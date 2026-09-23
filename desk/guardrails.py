from agents import Agent, GuardrailFunctionOutput, RunContextWrapper, output_guardrail

from desk.secrets_detect import looks_like_credential


@output_guardrail
async def no_secrets_guardrail(
    context: RunContextWrapper, agent: Agent, agent_output: str
) -> GuardrailFunctionOutput:
    """Refuses the finished report if it contains anything shaped like a
    credential copied out of the diff (FR-8). Runs after generation --
    the model call has already been paid for by the time this fires."""
    flagged = looks_like_credential(agent_output)
    return GuardrailFunctionOutput(
        output_info={"credential_shape_detected": flagged},
        tripwire_triggered=flagged,
    )
