import re

from desk.models import DiffChunk

_DIFF_GIT_RE = re.compile(r"^diff --git a/(?P<a>\S+) b/(?P<b>\S+)", re.MULTILINE)


def read_diff(path: str) -> str:
    """Reads a unified diff from `path`. Never raises: returns an
    "error: ..." message string on failure instead of propagating."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        return f"error: could not read diff at {path}: {exc}"


def split_diff(diff_text: str) -> list[DiffChunk] | str:
    """Splits a unified diff into one DiffChunk per file. Never raises:
    returns an "error: ..." message string for empty, propagated-error,
    or unparseable input instead of a chunk list."""
    if diff_text.startswith("error: "):
        return diff_text
    if not diff_text.strip():
        return "error: diff is empty"

    matches = list(_DIFF_GIT_RE.finditer(diff_text))
    if not matches:
        return "error: diff could not be parsed (no 'diff --git' headers found)"

    chunks = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(diff_text)
        chunks.append(DiffChunk(file=match.group("b"), patch=diff_text[start:end]))
    return chunks
