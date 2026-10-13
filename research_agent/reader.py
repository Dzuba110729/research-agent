import ipaddress
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura

from .models import FetchedPage

USER_AGENT = "research-agent/0.1"


def is_public_http(url: str) -> bool:
    """Пропускает только http(s) и не пускает на локальные адреса."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not host:
        return False
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return True  # это имя сайта, а не числовой адрес


class PageReader:
    def __init__(
        self,
        client: httpx.Client | None = None,
        max_bytes: int = 2_000_000,
        max_chars: int = 8000,
        min_chars: int = 80,
        max_redirects: int = 5,
    ):
        self._client = client or httpx.Client(
            timeout=15, headers={"User-Agent": USER_AGENT}
        )
        self._max_bytes = max_bytes
        self._max_chars = max_chars
        self._min_chars = min_chars
        self._max_redirects = max_redirects

    def fetch(self, url: str) -> FetchedPage | None:
        """Открывает страницу. Если не вышло или текста нет — возвращает None."""
        try:
            html, final_url = self._download(url)
        except httpx.HTTPError:
            return None
        if html is None:
            return None
        text = trafilatura.extract(html, url=final_url, include_comments=False)
        if not text or len(text.strip()) < self._min_chars:
            return None
        return FetchedPage(url=url, final_url=final_url, text=text.strip()[: self._max_chars])

    def _download(self, url: str) -> tuple[str | None, str]:
        current = url
        for _ in range(self._max_redirects + 1):
            if not is_public_http(current):
                return None, current
            with self._client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        return None, current
                    current = urljoin(current, location)
                    continue
                kind = response.headers.get("content-type", "").lower()
                if response.status_code != 200 or ("html" not in kind and "text" not in kind):
                    return None, current
                body = bytearray()
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > self._max_bytes:
                        return None, current
                return body.decode(response.encoding or "utf-8", errors="replace"), current
        return None, current
