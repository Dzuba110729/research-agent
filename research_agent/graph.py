import re
from dataclasses import dataclass
from typing import Protocol, TypedDict

from langgraph.graph import END, START, StateGraph

from .llm import LLM
from .models import FetchedPage, Limits, Page, normalize_url
from .verify import cited_ids, normalize_citations, verify_report


class Searcher(Protocol):
    def search(self, query: str) -> list[str]: ...


class Reader(Protocol):
    def fetch(self, url: str) -> FetchedPage | None: ...


@dataclass
class Deps:
    llm: LLM
    search: Searcher
    reader: Reader
    limits: Limits = Limits()


class State(TypedDict, total=False):
    question: str
    queries: list[str]
    round: int
    seen: list[str]
    candidates: list[str]
    pages: list[Page]
    draft: str
    attempts: int
    errors: list[str]
    warnings: list[str]
    status: str
    report: str


def build_graph(deps: Deps):
    lim = deps.limits

    def plan(state: State) -> State:
        queries = deps.llm.plan(state["question"], lim.max_queries)
        return {"queries": queries[: lim.max_queries]}

    def search(state: State) -> State:
        seen = list(state["seen"])
        warnings = list(state["warnings"])
        budget = lim.max_pages - len(state["pages"])
        candidates: list[str] = []
        for query in state["queries"]:
            try:
                urls = deps.search.search(query)
            except Exception as exc:  # сеть, ключ, лимиты Brave
                warnings.append(f"Поиск по запросу {query!r} не удался: {exc}")
                continue
            for url in urls:
                key = normalize_url(url)
                if key in seen or len(candidates) >= budget:
                    continue
                seen.append(key)
                candidates.append(url)
        return {
            "round": state["round"] + 1,
            "seen": seen,
            "candidates": candidates,
            "warnings": warnings,
        }

    def read(state: State) -> State:
        pages = list(state["pages"])
        known = {u for p in pages for u in p.known_urls()}
        for url in state["candidates"]:
            if len(pages) >= lim.max_pages:
                break
            fetched = deps.reader.fetch(url)
            if fetched is None:
                continue
            urls = {normalize_url(fetched.url), normalize_url(fetched.final_url)}
            if urls & known:
                continue
            pages.append(Page(f"S{len(pages) + 1}", fetched.url, fetched.final_url, fetched.text))
            known |= urls
        return {"pages": pages}

    def check(state: State) -> State:
        if not state["pages"] or state["round"] >= lim.max_rounds:
            return {"queries": []}
        complete, new_queries = deps.llm.assess(
            state["question"], state["pages"], lim.max_new_queries
        )
        return {"queries": [] if complete else new_queries}

    def after_check(state: State) -> str:
        if state["queries"]:
            return "search"
        return "draft" if state["pages"] else "reject_empty"

    def reject_empty(state: State) -> State:
        return {
            "status": "rejected",
            "errors": ["Ни одна страница не открылась, отчёт писать не из чего."],
        }

    def draft(state: State) -> State:
        text = deps.llm.write(state["question"], state["pages"], state["errors"])
        return {"draft": text, "attempts": state["attempts"] + 1}

    def verify(state: State) -> State:
        errors = verify_report(state["draft"], state["pages"])
        if not errors:
            return {"errors": [], "status": "verified"}
        if state["attempts"] >= lim.max_drafts:
            return {"errors": errors, "status": "rejected"}
        return {"errors": errors, "status": "retry"}

    def after_verify(state: State) -> str:
        return {"verified": "finalize", "retry": "draft"}.get(state["status"], END)

    def finalize(state: State) -> State:
        by_id = {p.id: p for p in state["pages"]}
        body = normalize_citations(state["draft"])
        body = re.sub(
            r"\[(S\d+)\]", lambda m: f"[[{m.group(1)}]]({by_id[m.group(1)].final_url})", body
        )
        used = cited_ids(state["draft"])
        sources = "\n".join(f"- [{sid}] {by_id[sid].final_url}" for sid in used)
        report = f"{body.rstrip()}\n\n## Источники\n\n{sources}\n"
        errors = verify_report(report, state["pages"])
        if errors:
            return {"status": "rejected", "errors": errors}
        return {"status": "accepted", "report": report}

    g = StateGraph(State)
    for name, fn in [
        ("plan", plan), ("search", search), ("read", read), ("check", check),
        ("reject_empty", reject_empty), ("draft", draft), ("verify", verify),
        ("finalize", finalize),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "plan")
    g.add_edge("plan", "search")
    g.add_edge("search", "read")
    g.add_edge("read", "check")
    g.add_conditional_edges("check", after_check, ["search", "draft", "reject_empty"])
    g.add_edge("reject_empty", END)
    g.add_edge("draft", "verify")
    g.add_conditional_edges("verify", after_verify, ["finalize", "draft", END])
    g.add_edge("finalize", END)
    return g.compile()


def run(question: str, deps: Deps) -> State:
    graph = build_graph(deps)
    return graph.invoke(
        {
            "question": question, "round": 0, "seen": [], "pages": [],
            "attempts": 0, "errors": [], "warnings": [], "queries": [],
            "candidates": [],
        }
    )
