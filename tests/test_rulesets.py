from desk.rulesets import load_ruleset


def test_load_ruleset_reads_existing_file():
    text = load_ruleset("default")

    assert "hardcoded credentials" in text


def test_load_ruleset_missing_file_falls_back_with_sensible_message():
    text = load_ruleset("does-not-exist")

    assert "not found" in text
    assert "hardcoded credentials" in text  # still usable fallback rules
