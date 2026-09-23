import re

_CREDENTIAL_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),  # OpenAI-style secret key
    re.compile(r"AIza[0-9A-Za-z_-]{35}"),  # Google API key
    re.compile(r"ghp_[A-Za-z0-9]{36}"),  # GitHub personal access token
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),  # bearer token
    re.compile(r"(?i)password\s*[:=]\s*\S+"),  # generic password assignment
]


def looks_like_credential(text: str) -> bool:
    """True if `text` contains a substring shaped like a leaked
    credential. Used by the output guardrail (FR-8) to refuse a report
    rather than let a secret copied out of the diff reach the user."""
    return any(pattern.search(text) for pattern in _CREDENTIAL_PATTERNS)
