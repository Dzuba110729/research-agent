import pytest

from research_agent.graph import Deps
from research_agent.models import FetchedPage, Limits

TEXT = "Это достаточно длинный текст страницы про исследуемую тему. " * 5


def page(url: str, final: str | None = None, text: str = TEXT) -> FetchedPage:
    return FetchedPage(url=url, final_url=final or url, text=text)


class FakeLLM:
    """Модель-подделка: отвечает по заранее заданному сценарию."""

    def __init__(self, queries=("q1",), assessments=((True, []),), drafts=("Факт [S1].",)):
        self.queries = list(queries)
        self.assessments = list(assessments)
        self.drafts = list(drafts)
        self.assess_calls = 0
        self.write_calls: list[list[str]] = []

    def plan(self, question, max_queries):
        return self.queries

    def assess(self, question, pages, max_new):
        i = min(self.assess_calls, len(self.assessments) - 1)
        self.assess_calls += 1
        return self.assessments[i]

    def write(self, question, pages, errors):
        self.write_calls.append(list(errors))
        i = min(len(self.write_calls) - 1, len(self.drafts) - 1)
        return self.drafts[i]


class FakeSearch:
    def __init__(self, results=None, default=()):
        self.results = results or {}
        self.default = list(default)
        self.queries: list[str] = []

    def search(self, query):
        self.queries.append(query)
        return self.results.get(query, self.default)


class FakeReader:
    def __init__(self, pages: dict[str, FetchedPage | None]):
        self.pages = pages
        self.fetched: list[str] = []

    def fetch(self, url):
        self.fetched.append(url)
        return self.pages.get(url)


@pytest.fixture
def make_deps():
    def _make(llm, search, reader, **limits):
        return Deps(llm=llm, search=search, reader=reader, limits=Limits(**limits))

    return _make
