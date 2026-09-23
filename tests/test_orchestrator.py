from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from desk.models import Finding
from desk.orchestrator import (
    _serialize_findings,
    render_footer,
    review_diff,
    review_with_cheaper_override,
    run_reviewers_concurrently,
)
from desk.hooks import FooterRunHooks, ReviewerStats


def test_serialize_findings_formats_each_line():
    findings = [Finding(file="a.py", line=3, severity="critical", message="hardcoded key")]

    text = _serialize_findings("security", findings)

    assert "### security" in text
    assert "[critical] a.py:3 -- hardcoded key" in text


def test_serialize_findings_empty_list():
    text = _serialize_findings("style", [])

    assert "(no findings)" in text


def test_render_footer_lists_every_reviewer():
    stats = [
        ReviewerStats("SecurityReviewer", 1200.0, 500, 100, 600),
        ReviewerStats("TestsReviewer", 900.0, 400, 80, 480),
    ]

    footer = render_footer(stats)

    assert "SecurityReviewer" in footer
    assert "TestsReviewer" in footer
    assert "600 tokens" in footer


@pytest.mark.asyncio
async def test_run_reviewers_concurrently_launches_all_three_as_one_group():
    agents = {
        "security_reviewer": SimpleNamespace(name="SecurityReviewer"),
        "tests_reviewer": SimpleNamespace(name="TestsReviewer"),
        "style_reviewer": SimpleNamespace(name="StyleReviewer"),
    }
    fake_result = SimpleNamespace(final_output=[])

    with patch("desk.orchestrator.run_and_log", new=AsyncMock(return_value=fake_result)) as mock_run:
        results = await run_reviewers_concurrently(agents, "diff text", context=None, hooks=FooterRunHooks())

    assert len(results) == 3
    assert mock_run.call_count == 3
    called_agents = {call.args[0].name for call in mock_run.call_args_list}
    assert called_agents == {"SecurityReviewer", "TestsReviewer", "StyleReviewer"}


@pytest.mark.asyncio
async def test_review_with_cheaper_override_does_not_mutate_agent_model(tmp_path):
    diff_file = tmp_path / "sample.diff"
    diff_file.write_text("diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x\n+y\n", encoding="utf-8")

    security = SimpleNamespace(name="SecurityReviewer", model="gpt-4o-mini")
    agents = {"security_reviewer": security}

    declared_result = SimpleNamespace(final_output=[])
    override_result = SimpleNamespace(final_output=[])
    mock_run = AsyncMock(side_effect=[declared_result, override_result])

    with patch("desk.orchestrator.Runner.run", new=mock_run):
        declared, override = await review_with_cheaper_override(
            str(diff_file), context=None, agents=agents, cheaper_model="gpt-3.5-turbo"
        )

    assert declared is declared_result
    assert override is override_result
    assert security.model == "gpt-4o-mini"  # never mutated

    first_call_kwargs = mock_run.call_args_list[0].kwargs
    second_call_kwargs = mock_run.call_args_list[1].kwargs
    assert "run_config" not in first_call_kwargs or first_call_kwargs.get("run_config") is None
    assert second_call_kwargs["run_config"].model == "gpt-3.5-turbo"


@pytest.mark.asyncio
async def test_review_diff_missing_file_short_circuits_before_any_model_call():
    with patch("desk.orchestrator.run_and_log", new=AsyncMock()) as mock_run:
        result = await review_diff("no/such/file.diff", context=None, agents={})

    assert result.startswith("error:")
    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_review_diff_empty_file_short_circuits_before_any_model_call(tmp_path):
    empty_diff = tmp_path / "empty.diff"
    empty_diff.write_text("", encoding="utf-8")

    with patch("desk.orchestrator.run_and_log", new=AsyncMock()) as mock_run:
        result = await review_diff(str(empty_diff), context=None, agents={})

    assert result.startswith("error:")
    mock_run.assert_not_called()
