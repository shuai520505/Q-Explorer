from src.research import redact_sensitive_text


def test_known_and_pattern_secrets_are_redacted():
    secret = "super-secret-value"
    text = f"Authorization: Bearer abcdefghijklmnop API_KEY={secret} token=othersecret"
    redacted = redact_sensitive_text(text, [secret])
    assert secret not in redacted and "abcdefghijklmnop" not in redacted and "othersecret" not in redacted
    assert redacted.count("[REDACTED]") >= 3

