import httpx

from research_agent.reader import PageReader, is_public_http
from research_agent.search import BraveSearch

HTML = "<html><body><article>" + "<p>Длинный абзац с полезным текстом о теме. </p>" * 20 + "</article></body></html>"


def reader_for(handler) -> PageReader:
    return PageReader(client=httpx.Client(transport=httpx.MockTransport(handler)))


def html_response(body=HTML, status=200, **kw):
    return httpx.Response(status, text=body, headers={"content-type": "text/html; charset=utf-8"}, **kw)


def test_06_redirect_keeps_both_urls():
    def handler(request):
        if request.url.host == "a.com":
            return httpx.Response(301, headers={"location": "https://b.com/page"})
        return html_response()

    result = reader_for(handler).fetch("https://a.com/")
    assert result is not None
    assert result.url == "https://a.com/"
    assert result.final_url == "https://b.com/page"


def test_08_404_gives_none():
    assert reader_for(lambda r: html_response(status=404)).fetch("https://a.com/") is None


def test_08_empty_text_gives_none():
    assert reader_for(lambda r: html_response("<html><body></body></html>")).fetch("https://a.com/") is None


def test_pdf_skipped():
    handler = lambda r: httpx.Response(200, content=b"%PDF", headers={"content-type": "application/pdf"})
    assert reader_for(handler).fetch("https://a.com/f.pdf") is None


def test_redirect_to_local_address_blocked():
    def handler(request):
        if request.url.host == "a.com":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})
        raise AssertionError("локальный адрес нельзя открывать")

    assert reader_for(handler).fetch("https://a.com/") is None


def test_public_url_check():
    assert is_public_http("https://example.com/a")
    assert not is_public_http("file:///etc/passwd")
    assert not is_public_http("http://localhost:8000")
    assert not is_public_http("http://192.168.1.5/")


def test_brave_returns_urls_and_sends_key():
    seen = {}

    def handler(request):
        seen["token"] = request.headers["X-Subscription-Token"]
        seen["q"] = request.url.params["q"]
        return httpx.Response(200, json={"web": {"results": [{"url": "https://a.com"}, {"title": "без адреса"}]}})

    search = BraveSearch("KEY", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert search.search("тест") == ["https://a.com"]
    assert seen == {"token": "KEY", "q": "тест"}
