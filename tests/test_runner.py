import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from desk.runner import run_and_log


class FakeAgent:
    name = "SecurityReviewer"


@pytest.mark.asyncio
async def test_run_and_log_appends_one_ledger_line(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    fake_result = SimpleNamespace(final_output=[object(), object()])

    with patch("desk.runner.Runner.run", new=AsyncMock(return_value=fake_result)):
        result = await run_and_log(FakeAgent(), "diff text", ledger_path=ledger_path)

    assert result is fake_result
    lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["agent"] == "SecurityReviewer"
    assert entry["findings"] == 2
    assert "ts" in entry
    assert "request_id" in entry
    assert isinstance(entry["ms"], int)


@pytest.mark.asyncio
async def test_run_and_log_appends_without_overwriting(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    fake_result = SimpleNamespace(final_output=[])

    with patch("desk.runner.Runner.run", new=AsyncMock(return_value=fake_result)):
        await run_and_log(FakeAgent(), "diff 1", ledger_path=ledger_path)
        await run_and_log(FakeAgent(), "diff 2", ledger_path=ledger_path)

    lines = ledger_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
