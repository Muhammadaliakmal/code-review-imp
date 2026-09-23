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


def build_instructions(focus: str, language: str, strictness: str) -> str:
    """Assembles a reviewer's system prompt at request time from the
    language and strictness in context (FR-4). Gets terser under strict
    mode instead of just adding more rules on top. Deliberately does
    NOT embed the ruleset text -- the reviewer calls read_ruleset for
    that (FR-2, FR-9), so nothing from the context is baked into the
    prompt string itself."""
    role_focus = FOCUS_BY_REVIEWER[focus]

    if strictness == "strict":
        return (
            f"You are a terse {focus} code reviewer for {language} code. "
            f"{role_focus} "
            "Call read_ruleset once at the start of the review and follow "
            "it. Report only findings you are confident about. No "
            "preamble, no praise, no summary -- findings only."
        )

    return (
        f"You are a {focus} code reviewer for {language} code, reviewing a "
        "unified diff.\n\n"
        f"{role_focus}\n\n"
        "Call read_ruleset first to load this repository's rules, then "
        "read the diff carefully and report every issue you find, even "
        "minor ones. Explain your reasoning briefly for each finding."
    )
