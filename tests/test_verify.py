from research_agent.models import Page
from research_agent.verify import verify_report

PAGES = [
    Page("S1", "https://a.com/x", "https://a.com/x", "t"),
    Page("S2", "https://b.com", "https://c.com/final", "t"),
]


def test_01_valid_citation_accepted():
    assert verify_report("Факт [S1].", PAGES) == []


def test_04_unknown_id_rejected():
    errors = verify_report("Факт [S9].", PAGES)
    assert any("S9" in e for e in errors)


def test_05_no_citations_rejected():
    assert verify_report("Текст без ссылок.", PAGES)


def test_03_url_not_opened_rejected():
    errors = verify_report("Факт [S1]. Подробнее: https://evil.com/x.", PAGES)
    assert any("evil.com" in e for e in errors)


def test_markdown_link_without_scheme_rejected():
    errors = verify_report("Факт [S1]. [тут](evil.com/x)", PAGES)
    assert any("evil.com" in e for e in errors)


def test_06_redirect_both_urls_known():
    text = "Факт [S2]. https://b.com и https://c.com/final и https://c.com/final/."
    assert verify_report(text, PAGES) == []


def test_group_citation_checked():
    errors = verify_report("Факт [S1, S7].", PAGES)
    assert any("S7" in e for e in errors)
