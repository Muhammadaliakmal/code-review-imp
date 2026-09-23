from agents import RunContextWrapper

from desk.agents import build_agents
from desk.context import ReviewContext

FAKE_MODEL = "gemini-2.5-flash"


def test_three_reviewers_are_clones_of_base_with_own_settings():
    agents = build_agents(model=FAKE_MODEL)
    base, sec, tests, style = (
        agents["base_reviewer"],
        agents["security_reviewer"],
        agents["tests_reviewer"],
        agents["style_reviewer"],
    )

    for reviewer in (sec, tests, style):
        assert reviewer.output_type is base.output_type
        assert [t.name for t in reviewer.tools] == [t.name for t in base.tools]

    assert sec.name != tests.name != style.name
    assert sec.model_settings.tool_choice == "read_ruleset"
    assert tests.model_settings.tool_choice != "read_ruleset"


def test_security_reviewer_forced_to_read_ruleset_tool():
    agents = build_agents(model=FAKE_MODEL)

    assert agents["security_reviewer"].model_settings.tool_choice == "read_ruleset"


def test_desk_has_merge_tool_and_remediation_handoff():
    agents = build_agents(model=FAKE_MODEL)
    desk = agents["desk"]

    assert "merge_findings" in [t.name for t in desk.tools]
    assert agents["remediation_specialist"] in desk.handoffs
    assert desk.output_guardrails, "Desk must carry the no-secrets output guardrail"


def test_reviewer_instructions_differ_by_focus_and_strictness():
    agents = build_agents(model=FAKE_MODEL)
    sec, style = agents["security_reviewer"], agents["style_reviewer"]

    normal_ctx = RunContextWrapper(
        context=ReviewContext(repo="r", language="python", ruleset_id="default", strictness="normal")
    )
    strict_ctx = RunContextWrapper(
        context=ReviewContext(repo="r", language="python", ruleset_id="default", strictness="strict")
    )

    sec_prompt = sec.instructions(normal_ctx, sec)
    style_prompt = style.instructions(normal_ctx, style)
    sec_strict_prompt = sec.instructions(strict_ctx, sec)

    assert sec_prompt != style_prompt
    assert sec_prompt != sec_strict_prompt
    assert len(sec_strict_prompt) < len(sec_prompt)
    assert "r" not in sec_prompt.split()  # repo name never baked into the prompt
