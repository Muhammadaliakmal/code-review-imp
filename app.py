import asyncio

import chainlit as cl
from agents import ItemHelpers, MaxTurnsExceeded, OutputGuardrailTripwireTriggered, Runner, trace
from dotenv import load_dotenv
from openai.types.responses import ResponseTextDeltaEvent

from desk.agents import build_agents
from desk.config import build_gemini_model, configure_tracing
from desk.context import ReviewContext
from desk.diff import split_diff
from desk.hooks import FooterRunHooks
from desk.orchestrator import MAX_TURNS, _serialize_findings, render_footer
from desk.runner import run_and_log

load_dotenv()
configure_tracing()
_MODEL = build_gemini_model()
_AGENTS = build_agents(_MODEL)

REVIEWER_KEYS = ("security_reviewer", "tests_reviewer", "style_reviewer")
REVIEWER_LABELS = {"security_reviewer": "security", "tests_reviewer": "tests", "style_reviewer": "style"}


@cl.on_chat_start
async def on_chat_start() -> None:
    """Session state holds the context and the last report (FR-12)."""
    cl.user_session.set(
        "context",
        ReviewContext(repo="chainlit-session", language="python", ruleset_id="default"),
    )
    cl.user_session.set("last_report", None)
    await cl.Message(
        content="Paste a unified diff and I'll run the security, tests, and style reviewers on it."
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    diff_text = message.content
    chunks = split_diff(diff_text)
    if isinstance(chunks, str):
        await cl.Message(content=chunks).send()
        return

    context = cl.user_session.get("context")
    hooks = FooterRunHooks()

    with trace(workflow_name="code-review-desk-chainlit"):
        tasks = {
            asyncio.ensure_future(
                run_and_log(_AGENTS[key], diff_text, context=context, hooks=hooks, max_turns=MAX_TURNS)
            ): REVIEWER_LABELS[key]
            for key in REVIEWER_KEYS
        }

        results = {}
        pending = set(tasks)
        try:
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    name = tasks[task]
                    result = task.result()
                    results[name] = result
                    await cl.Message(
                        content=_serialize_findings(name, result.final_output),
                        author=name,
                    ).send()
        except MaxTurnsExceeded:
            for task in pending:
                task.cancel()
            await cl.Message(content="Partial review: a reviewer exceeded the turn ceiling.").send()
            return

        combined_findings = "\n\n".join(
            _serialize_findings(name, results[name].final_output) for name in ("security", "tests", "style")
        )
        desk_input = f"Diff:\n{diff_text}\n\nCombined findings:\n{combined_findings}"

        desk_msg = cl.Message(content="", author="Desk")
        await desk_msg.send()

        try:
            streamed = Runner.run_streamed(
                _AGENTS["desk"], desk_input, context=context, hooks=hooks, max_turns=MAX_TURNS
            )
            async for event in streamed.stream_events():
                if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
                    await desk_msg.stream_token(event.data.delta)
            report_text = streamed.final_output
        except OutputGuardrailTripwireTriggered:
            desk_msg.content = "Review withheld: the report appeared to contain a credential copied from the diff."
            await desk_msg.update()
            return
        except MaxTurnsExceeded:
            desk_msg.content = "Partial review: the Desk exceeded the turn ceiling before finishing."
            await desk_msg.update()
            return

        await desk_msg.update()

    footer = render_footer(hooks.stats)
    await cl.Message(content=footer).send()
    cl.user_session.set("last_report", str(report_text) + footer)
