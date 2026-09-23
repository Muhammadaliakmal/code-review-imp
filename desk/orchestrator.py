import asyncio
import time

from agents import MaxTurnsExceeded, OutputGuardrailTripwireTriggered, RunConfig, Runner, trace

from desk.diff import read_diff, split_diff
from desk.hooks import FooterRunHooks
from desk.models import Finding
from desk.runner import run_and_log

MAX_TURNS = 12  # generous enough for read-ruleset + reason + respond,
# tight enough to catch a reviewer looping on tool calls (FR-9). Raised
# from an initial 8 after live testing against gpt-4o-mini showed
# occasional (non-deterministic, not reviewer-specific) runs taking
# more turns to converge on structured list[Finding] output.


def _serialize_findings(reviewer_name: str, findings: list[Finding]) -> str:
    if not findings:
        return f"### {reviewer_name}\n(no findings)"
    lines = [f"### {reviewer_name}"]
    lines += [f"- [{f.severity}] {f.file}:{f.line} -- {f.message}" for f in findings]
    return "\n".join(lines)


def render_footer(stats) -> str:
    lines = ["", "---", "**Review stats**"]
    for s in stats:
        lines.append(
            f"- {s.agent_name}: {s.ms:.0f}ms, {s.total_tokens} tokens "
            f"({s.input_tokens} in / {s.output_tokens} out)"
        )
    return "\n".join(lines)


async def run_reviewers_concurrently(agents, diff_text, context, hooks, *, max_turns=MAX_TURNS):
    """FR-5: three reviewers launched together and awaited as a group."""
    security, tests_reviewer, style = (
        agents["security_reviewer"],
        agents["tests_reviewer"],
        agents["style_reviewer"],
    )
    return await asyncio.gather(
        run_and_log(security, diff_text, context=context, hooks=hooks, max_turns=max_turns),
        run_and_log(tests_reviewer, diff_text, context=context, hooks=hooks, max_turns=max_turns),
        run_and_log(style, diff_text, context=context, hooks=hooks, max_turns=max_turns),
    )


async def run_reviewers_sequentially(agents, diff_text, context, *, max_turns=MAX_TURNS):
    """Sequential baseline, used only to produce the FR-5 comparison
    number -- never the path a real review takes."""
    results = []
    for reviewer in (
        agents["security_reviewer"],
        agents["tests_reviewer"],
        agents["style_reviewer"],
    ):
        results.append(await Runner.run(reviewer, diff_text, context=context, max_turns=max_turns))
    return results


async def measure_concurrency(agents, diff_text, context) -> dict:
    """FR-5's done-condition: both wall-clock numbers, side by side."""
    started = time.monotonic()
    await run_reviewers_concurrently(agents, diff_text, context, FooterRunHooks())
    concurrent_s = time.monotonic() - started

    started = time.monotonic()
    await run_reviewers_sequentially(agents, diff_text, context)
    sequential_s = time.monotonic() - started

    return {"concurrent_s": concurrent_s, "sequential_s": sequential_s}


async def review_diff(diff_path: str, context, agents: dict) -> str:
    """The full pipeline: split -> fan out -> merge-or-handoff -> guardrail
    -> footer. One trace covers the whole thing (FR-13)."""
    diff_text = read_diff(diff_path)
    if diff_text.startswith("error: "):
        return diff_text

    chunks = split_diff(diff_text)
    if isinstance(chunks, str):
        return chunks

    hooks = FooterRunHooks()

    with trace(workflow_name="code-review-desk"):
        try:
            security_result, tests_result, style_result = await run_reviewers_concurrently(
                agents, diff_text, context, hooks
            )
        except MaxTurnsExceeded:
            return "Partial review: a reviewer exceeded the turn ceiling before finishing."

        combined_findings = "\n\n".join(
            [
                _serialize_findings("security", security_result.final_output),
                _serialize_findings("tests", tests_result.final_output),
                _serialize_findings("style", style_result.final_output),
            ]
        )

        # A small model reading free-form finding text is unreliable at
        # the literal "is any severity exactly 'critical'" check -- it
        # tends to escalate on alarming *wording* (e.g. "security issue"
        # inside a minor finding's message) regardless of instructions.
        # So the orchestrator computes the real answer once, from the
        # actual Finding objects, and hands it to the Desk as a directive
        # instead of asking the model to re-derive it from prose. The
        # Desk still calls merge_findings itself (this call is separate
        # and only feeds the directive) -- FR-6's "Desk calls merge as a
        # tool" architecture is unchanged.
        precheck_merge = await run_and_log(
            agents["merge_specialist"], combined_findings, context=context, hooks=hooks, max_turns=MAX_TURNS
        )
        has_critical = any(f.severity == "critical" for f in precheck_merge.final_output)
        directive = (
            f"PRE-COMPUTED RESULT (ground truth, do not re-derive): "
            f"has_critical_security_finding = {has_critical}. "
            f"{'Hand off to RemediationSpecialist.' if has_critical else 'Do NOT hand off -- render the report yourself.'}"
        )

        desk_input = f"{directive}\n\nDiff:\n{diff_text}\n\nCombined findings:\n{combined_findings}"

        try:
            desk_result = await run_and_log(
                agents["desk"], desk_input, context=context, hooks=hooks, max_turns=MAX_TURNS
            )
        except OutputGuardrailTripwireTriggered:
            return "Review withheld: the report appeared to contain a credential copied from the diff."
        except MaxTurnsExceeded:
            return "Partial review: the Desk exceeded the turn ceiling before finishing."

    return str(desk_result.final_output) + render_footer(hooks.stats)


async def review_with_cheaper_override(diff_path: str, context, agents: dict, cheaper_model: str):
    """FR-7: same reviewer object, one run on its declared model, one
    on a run-level override -- no agent definition changes."""
    diff_text = read_diff(diff_path)
    security = agents["security_reviewer"]

    declared = await Runner.run(security, diff_text, context=context, max_turns=MAX_TURNS)
    override = await Runner.run(
        security,
        diff_text,
        context=context,
        max_turns=MAX_TURNS,
        run_config=RunConfig(model=cheaper_model),
    )
    return declared, override
