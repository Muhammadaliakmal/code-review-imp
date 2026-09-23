import asyncio
import sys

from dotenv import load_dotenv

from desk.agents import build_agents
from desk.config import configure_openai, configure_tracing
from desk.context import ReviewContext
from desk.orchestrator import review_diff


async def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: python main.py <diff-path> [--strict]")

    diff_path = sys.argv[1]
    strictness = "strict" if "--strict" in sys.argv else "normal"

    configure_tracing()
    model = configure_openai()
    agents = build_agents(model)

    context = ReviewContext(
        repo="local",
        language="python",
        ruleset_id="default",
        strictness=strictness,
    )

    report = await review_diff(diff_path, context, agents)
    print(report)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
