import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agents import Runner

LEDGER_PATH = Path(__file__).resolve().parent.parent / "ledger.jsonl"


def append_ledger(entry: dict, ledger_path: Path | None = None) -> None:
    path = ledger_path or LEDGER_PATH
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


async def run_and_log(agent, input_text, *, context=None, ledger_path: Path | None = None, **kwargs):
    """Wraps Runner.run and appends one ledger line per call (FR-11).

    Not a Runner subclass: this SDK's AgentRunner is explicitly marked
    experimental/not-for-subclassing in its own source, so every
    orchestrator call site uses this wrapper in place of Runner.run
    directly. No Agent definition references it -- removing a call
    site's use of run_and_log (swapping back to Runner.run) is the
    only change needed to disable the ledger for that call.
    """
    request_id = f"rev_{uuid4().hex[:8]}"
    started = time.monotonic()
    result = await Runner.run(agent, input_text, context=context, **kwargs)
    elapsed_ms = round((time.monotonic() - started) * 1000)

    findings_count = len(result.final_output) if isinstance(result.final_output, list) else 0
    append_ledger(
        {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "request_id": request_id,
            "agent": agent.name,
            "ms": elapsed_ms,
            "findings": findings_count,
        },
        ledger_path=ledger_path,
    )
    return result
