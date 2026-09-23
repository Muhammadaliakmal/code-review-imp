from pathlib import Path

RULESETS_DIR = Path(__file__).resolve().parent.parent / "rulesets"

_FALLBACK_RULES = (
    "- Flag hardcoded credentials, API keys, or tokens.\n"
    "- Flag missing input validation on functions handling external data.\n"
    "- Flag new public functions with no accompanying test.\n"
)


def load_ruleset(ruleset_id: str) -> str:
    """Reads rulesets/<ruleset_id>.md. Never raises: falls back to a
    built-in minimal ruleset with an explanatory note if the file is
    missing or unreadable (FR-9's "deleting the ruleset file still
    produces a review that finishes with a sensible message")."""
    path = RULESETS_DIR / f"{ruleset_id}.md"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return (
            f"(ruleset '{ruleset_id}' not found, using built-in defaults)\n\n"
            + _FALLBACK_RULES
        )
