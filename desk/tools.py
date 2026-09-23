from agents import RunContextWrapper, function_tool

from desk.context import ReviewContext
from desk.rulesets import load_ruleset


@function_tool
async def read_ruleset(wrapper: RunContextWrapper[ReviewContext]) -> str:
    """Reads the ruleset for this repository's configured ruleset_id.
    Takes no repo/ruleset_id parameter -- both come from the run
    context, so neither ever appears in the generated tool schema or
    in prompt text (FR-2)."""
    return load_ruleset(wrapper.context.ruleset_id)
