from desk.secrets_detect import looks_like_credential


def test_detects_openai_style_key():
    assert looks_like_credential("here is the key sk-abcdefghijklmnopqrstuvwx used in prod")


def test_detects_aws_key():
    assert looks_like_credential("AKIAABCDEFGHIJKLMNOP was hardcoded")


def test_detects_generic_password_assignment():
    assert looks_like_credential('password = "hunter2"')


def test_clean_report_is_not_flagged():
    assert not looks_like_credential(
        "SecurityReviewer found 2 issues: missing input validation on line 40."
    )
