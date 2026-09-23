from desk.prompts import build_instructions

RULESET = "- Flag hardcoded credentials.\n"


def test_normal_and_strict_prompts_visibly_differ():
    normal = build_instructions("security", RULESET, "python", "normal")
    strict = build_instructions("security", RULESET, "python", "strict")

    assert normal != strict
    assert len(strict) < len(normal)


def test_repo_name_never_appears_in_prompt():
    prompt = build_instructions("security", RULESET, "python", "normal")

    assert "acme-corp-internal-repo" not in prompt


def test_ruleset_text_is_included():
    prompt = build_instructions("style", RULESET, "python", "normal")

    assert "hardcoded credentials" in prompt
