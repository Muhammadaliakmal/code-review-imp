import pytest

from desk.guardrails import no_secrets_guardrail


@pytest.mark.asyncio
async def test_guardrail_trips_on_leaked_credential():
    leaky_output = "Here is the key: AKIAABCDEFGHIJKLMNOP was hardcoded in config.py"

    result = await no_secrets_guardrail.run(None, None, leaky_output)

    assert result.output.tripwire_triggered is True
    assert result.output.output_info["credential_shape_detected"] is True


@pytest.mark.asyncio
async def test_guardrail_passes_clean_report():
    clean_output = "SecurityReviewer found a hardcoded AWS key in config.py"

    result = await no_secrets_guardrail.run(None, None, clean_output)

    assert result.output.tripwire_triggered is False
    assert result.output.output_info["credential_shape_detected"] is False
