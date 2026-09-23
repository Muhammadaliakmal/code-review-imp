import os
import sys

from agents import set_tracing_export_api_key

MODEL_NAME = "gpt-4o-mini"


def require_env(name: str) -> str:
    """Fails fast at startup with a one-sentence message, never a stack
    trace, if a required key is missing (constitution.md §2)."""
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing required environment variable: {name}. Set it in .env and try again.")
    return value


def configure_openai() -> str:
    """The one place the model name is set -- every agent points at
    this string, satisfying FR-1's "configured on the agent"
    (constitution.md §1). The SDK's default model provider reads
    OPENAI_API_KEY from the environment itself, so this just fails
    fast if it's missing rather than letting a later call fail
    obscurely."""
    require_env("OPENAI_API_KEY")
    return MODEL_NAME


def configure_tracing() -> None:
    """FR-13: tracing exported under the project's own key."""
    set_tracing_export_api_key(require_env("OPENAI_API_KEY"))
