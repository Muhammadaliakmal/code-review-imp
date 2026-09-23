FOCUS_BY_REVIEWER = {
    "security": (
        "Focus on security: hardcoded credentials, injection risks, unsafe "
        "deserialization, missing auth checks, unvalidated external input."
    ),
    "tests": (
        "Focus on test coverage: new or changed public functions with no "
        "accompanying test, weakened assertions, deleted test cases."
    ),
    "style": (
        "Focus on style and convention: naming consistency, function length, "
        "dead code, deviations from the repo's existing patterns."
    ),
}


def build_instructions(focus: str, ruleset_text: str, language: str, strictness: str) -> str:
    """Assembles a reviewer's system prompt at request time from the
    ruleset and language in context (FR-4). Gets terser under strict
    mode instead of just adding more rules on top."""
    role_focus = FOCUS_BY_REVIEWER[focus]

    if strictness == "strict":
        return (
            f"You are a terse {focus} code reviewer for {language} code. "
            f"{role_focus} "
            "Report only findings you are confident about. No preamble, "
            "no praise, no summary -- findings only.\n\n"
            f"Ruleset:\n{ruleset_text}"
        )

    return (
        f"You are a {focus} code reviewer for {language} code, reviewing a "
        "unified diff.\n\n"
        f"{role_focus}\n\n"
        "Read the diff carefully and report every issue you find, even "
        "minor ones. Explain your reasoning briefly for each finding.\n\n"
        f"Ruleset for this repository:\n{ruleset_text}"
    )
