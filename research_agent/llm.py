import json
import os
from typing import Protocol

from .models import Page
from .safety import SYSTEM_PROMPT, wrap_untrusted

DEFAULT_MODEL = "claude-sonnet-5-5"


class LLM(Protocol):
    def plan(self, question: str, max_queries: int) -> list[str]: ...

    def assess(
        self, question: str, pages: list[Page], max_new: int
    ) -> tuple[bool, list[str]]: ...

    def write(self, question: str, pages: list[Page], errors: list[str]) -> str: ...


def parse_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"Модель не вернула JSON: {text[:200]!r}")
    return json.loads(text[start : end + 1])


def _clean_queries(raw: object, limit: int) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        q = str(item).strip()
        if q and q not in out:
            out.append(q)
    return out[:limit]


class ClaudeLLM:
    def __init__(self, client=None, model: str | None = None):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self._client = client
        self._model = model or os.environ.get("RESEARCH_MODEL", DEFAULT_MODEL)

    def _ask(self, user: str, max_tokens: int = 2000) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in message.content if b.type == "text")

    def plan(self, question: str, max_queries: int) -> list[str]:
        reply = self._ask(
            f"Вопрос пользователя:\n{question}\n\n"
            f"Составь от 3 до {max_queries} разных поисковых запросов для веб-поиска. "
            'Верни только JSON: {"queries": ["...", "..."]}'
        )
        return _clean_queries(parse_json(reply).get("queries"), max_queries)

    def assess(
        self, question: str, pages: list[Page], max_new: int
    ) -> tuple[bool, list[str]]:
        sources = "\n".join(wrap_untrusted(p.id, p.text, limit=1500) for p in pages)
        reply = self._ask(
            f"Вопрос пользователя:\n{question}\n\nСобранные материалы:\n{sources}\n\n"
            "Хватает ли материалов, чтобы полно ответить на вопрос? "
            f"Если нет, предложи до {max_new} новых поисковых запросов. "
            'Верни только JSON: {"complete": true|false, "new_queries": ["..."]}'
        )
        data = parse_json(reply)
        return bool(data.get("complete")), _clean_queries(data.get("new_queries"), max_new)

    def write(self, question: str, pages: list[Page], errors: list[str]) -> str:
        sources = "\n".join(wrap_untrusted(p.id, p.text) for p in pages)
        fix = ""
        if errors:
            fix = "\n\nПрошлый черновик отклонён. Исправь ошибки:\n- " + "\n- ".join(errors)
        return self._ask(
            f"Вопрос пользователя:\n{question}\n\nМатериалы:\n{sources}\n\n"
            "Напиши отчёт в Markdown на языке вопроса. Каждое утверждение с фактом "
            "подкрепи ссылкой [S1]. Используй только номера из материалов. "
            "Не пиши адреса сайтов."
            + fix,
            max_tokens=4000,
        )
