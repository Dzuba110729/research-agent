from dataclasses import dataclass, field
from urllib.parse import urlsplit


def normalize_url(url: str) -> str:
    """Приводит адрес к одному виду, чтобы сравнивать адреса символ в символ."""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    query = f"?{parts.query}" if parts.query else ""
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}{query}"


@dataclass(frozen=True)
class FetchedPage:
    url: str
    final_url: str
    text: str


@dataclass(frozen=True)
class Page:
    id: str
    url: str
    final_url: str
    text: str

    def known_urls(self) -> set[str]:
        return {normalize_url(self.url), normalize_url(self.final_url)}


@dataclass(frozen=True)
class Limits:
    max_pages: int = 15
    max_rounds: int = 3
    max_drafts: int = 2
    max_queries: int = 6
    max_new_queries: int = 3
