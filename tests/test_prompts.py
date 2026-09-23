from desk.prompts import build_instructions


def test_normal_and_strict_prompts_visibly_differ():
    normal = build_instructions("security", "python", "normal")
    strict = build_instructions("security", "python", "strict")

    assert normal != strict
    assert len(strict) < len(normal)


def test_repo_specific_details_never_baked_into_prompt():
    prompt = build_instructions("security", "python", "normal")

    assert "acme-corp-internal-repo" not in prompt


def test_prompt_tells_reviewer_to_call_ruleset_tool():
    prompt = build_instructions("style", "python", "normal")

    assert "read_ruleset" in prompt
