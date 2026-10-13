"""Проверка ссылок отчёта. Обычный код, без модели."""
import re

from .models import Page, normalize_url

_GROUP_RE = re.compile(r"\[\s*(S\d+(?:\s*[,;]\s*S\d+)+)\s*\]")
_CITE_RE = re.compile(r"\[S(\d+)\]")
_MD_LINK_ON_CITE_RE = re.compile(r"(\[S\d+\])\([^)]*\)")
_URL_RE = re.compile(r"https?://[^\s<>)\]\"']+", re.IGNORECASE)
_MD_TARGET_RE = re.compile(r"\]\(\s*([^)\s]+)\s*\)")


def normalize_citations(text: str) -> str:
    """[S1, S2] -> [S1] [S2]; [S1](url) -> [S1]."""
    text = _GROUP_RE.sub(
        lambda m: " ".join(f"[{s.strip()}]" for s in re.split(r"[,;]", m.group(1))),
        text,
    )
    return _MD_LINK_ON_CITE_RE.sub(r"\1", text)


def cited_ids(text: str) -> list[str]:
    seen: list[str] = []
    for m in _CITE_RE.finditer(normalize_citations(text)):
        sid = f"S{m.group(1)}"
        if sid not in seen:
            seen.append(sid)
    return seen


def verify_report(text: str, pages: list[Page]) -> list[str]:
    """Возвращает список ошибок. Пустой список — отчёт принят."""
    errors: list[str] = []
    registry = {p.id: p for p in pages}
    known_urls = {u for p in pages for u in p.known_urls()}
    normalized = normalize_citations(text)

    ids = cited_ids(text)
    if not ids:
        errors.append("В отчёте нет ни одной ссылки вида [S1].")
    for sid in ids:
        if sid not in registry:
            errors.append(f"Ссылка [{sid}] не найдена среди открытых страниц.")

    found = {m.group(0).rstrip(".,;:") for m in _URL_RE.finditer(normalized)}
    found |= {m.group(1) for m in _MD_TARGET_RE.finditer(normalized)}
    for url in sorted(found):
        if normalize_url(url) not in known_urls:
            errors.append(f"Адрес {url} агент не открывал.")
    return errors
