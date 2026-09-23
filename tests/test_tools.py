import asyncio

from agents.run import RunConfig
from agents.tool_context import ToolContext

from desk.context import ReviewContext
from desk.tools import read_ruleset


def test_read_ruleset_schema_has_no_wrapper_parameter():
    schema = read_ruleset.params_json_schema

    assert schema["properties"] == {}
    assert "ruleset_id" not in schema["properties"]
    assert "repo" not in schema["properties"]


def test_read_ruleset_reads_via_context_not_args():
    ctx = ReviewContext(repo="acme-corp-internal-repo", language="python", ruleset_id="default")
    tool_ctx = ToolContext(
        context=ctx,
        tool_name="read_ruleset",
        tool_call_id="call_1",
        tool_arguments="{}",
        run_config=RunConfig(),
    )

    result = asyncio.run(read_ruleset.on_invoke_tool(tool_ctx, "{}"))

    assert "hardcoded credentials" in result
    assert "acme-corp-internal-repo" not in result
