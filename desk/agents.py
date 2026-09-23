from agents import Agent, ModelSettings

from desk.context import ReviewContext
from desk.guardrails import no_secrets_guardrail
from desk.hooks import SecurityToolAgentHooks
from desk.models import Finding
from desk.prompts import build_instructions
from desk.tools import read_ruleset


def _reviewer_instructions(focus: str):
    def _build(wrapper, agent) -> str:
        ctx: ReviewContext = wrapper.context
        return build_instructions(focus, ctx.language, ctx.strictness)

    return _build


def build_agents(model):
    """Constructs every agent in the pipeline against a single shared
    `model` (gemini-2.5-flash configured once, per constitution.md
    §1). Returns a namespace-style dict so callers import symbols by
    name without re-instantiating agents per call."""

    base_reviewer = Agent[ReviewContext](
        name="BaseReviewer",
        tools=[read_ruleset],
        output_type=list[Finding],
        model=model,
    )

    security_hooks = SecurityToolAgentHooks()
    security_reviewer = base_reviewer.clone(
        name="SecurityReviewer",
        instructions=_reviewer_instructions("security"),
        model_settings=ModelSettings(tool_choice="read_ruleset", temperature=0.2),
        hooks=security_hooks,
    )

    tests_reviewer = base_reviewer.clone(
        name="TestsReviewer",
        instructions=_reviewer_instructions("tests"),
        model_settings=ModelSettings(temperature=0.3),
    )

    style_reviewer = base_reviewer.clone(
        name="StyleReviewer",
        instructions=_reviewer_instructions("style"),
        model_settings=ModelSettings(temperature=0.3),
    )

    merge_specialist = Agent[ReviewContext](
        name="MergeSpecialist",
        instructions=(
            "You receive findings from three reviewers (security, tests, "
            "style) as a single list, possibly with overlapping findings "
            "for the same file/line. Deduplicate findings that describe "
            "the same underlying issue (same file, same or adjacent line, "
            "same concern), keeping the clearer message. Order the "
            "remaining findings critical first, then major, then minor."
        ),
        output_type=list[Finding],
        model=model,
    )

    remediation_specialist = Agent[ReviewContext](
        name="RemediationSpecialist",
        handoff_description="Proposes a patch for a critical security finding.",
        instructions=(
            "You are given a diff and a critical security finding raised "
            "against it. Propose a minimal, concrete patch that fixes the "
            "finding. Explain briefly why the original code was unsafe. "
            "You are talking directly to the developer -- be specific and "
            "actionable, not generic advice."
        ),
        model=model,
    )

    merge_tool = merge_specialist.as_tool(
        tool_name="merge_findings",
        tool_description=(
            "Deduplicates overlapping findings from the security, tests, "
            "and style reviewers and orders them by severity. Pass all "
            "three reviewers' findings, combined, as the input."
        ),
    )

    desk = Agent[ReviewContext](
        name="Desk",
        instructions=(
            "You are given the diff and the raw findings from three "
            "reviewers (security, tests, style), combined into one list. "
            "First, call merge_findings with that combined list to "
            "deduplicate and severity-order it -- you keep the "
            "conversation after this call, it is a tool, not a transfer. "
            "Then: if any merged finding has severity 'critical' and "
            "concerns a security issue (secrets, injection, auth, unsafe "
            "deserialization), hand off to RemediationSpecialist so it can "
            "propose a fix -- do not render a report yourself in that "
            "case, the handoff takes over the conversation. Otherwise, "
            "render the merged findings as a single markdown report, "
            "grouped by severity (critical, major, minor), each line as "
            "'- [severity] file:line -- message'. Never include the "
            "literal text of any credential, token, or password found in "
            "the diff -- describe the finding without quoting the secret."
        ),
        tools=[merge_tool],
        handoffs=[remediation_specialist],
        output_guardrails=[no_secrets_guardrail],
        output_type=str,
        model=model,
    )

    return {
        "base_reviewer": base_reviewer,
        "security_reviewer": security_reviewer,
        "tests_reviewer": tests_reviewer,
        "style_reviewer": style_reviewer,
        "merge_specialist": merge_specialist,
        "remediation_specialist": remediation_specialist,
        "desk": desk,
        "security_hooks": security_hooks,
    }
