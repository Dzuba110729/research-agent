import argparse
import os
import sys
from pathlib import Path

from .graph import Deps, run
from .llm import ClaudeLLM
from .models import Limits
from .reader import PageReader
from .search import BraveSearch


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research_agent")
    parser.add_argument("question")
    parser.add_argument("--out", default="report.md")
    parser.add_argument("--max-pages", type=int, default=15)
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args(argv)

    missing = [k for k in ("BRAVE_API_KEY", "ANTHROPIC_API_KEY") if not os.environ.get(k)]
    if missing:
        print(f"Не заданы переменные окружения: {', '.join(missing)}", file=sys.stderr)
        return 2

    deps = Deps(
        llm=ClaudeLLM(),
        search=BraveSearch(os.environ["BRAVE_API_KEY"]),
        reader=PageReader(),
        limits=Limits(max_pages=args.max_pages, max_rounds=args.max_rounds),
    )
    result = run(args.question, deps)

    for warning in result.get("warnings", []):
        print(f"Предупреждение: {warning}", file=sys.stderr)
    if result["status"] == "accepted":
        Path(args.out).write_text(result["report"], encoding="utf-8")
        print(f"Отчёт сохранён: {args.out} (страниц открыто: {len(result['pages'])})")
        return 0
    print("Отчёт отклонён:", file=sys.stderr)
    for error in result.get("errors", []):
        print(f"- {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
