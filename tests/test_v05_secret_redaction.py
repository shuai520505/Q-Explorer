from src.v05_gate0 import redact_secrets


def test_v05_secret_redaction_is_recursive():
    value = {"access_key": "sensitive", "nested": {"api_key": "sensitive", "device_id": "D1"}}
    redacted = redact_secrets(value)
    assert redacted["access_key"] == "***REDACTED***"
    assert redacted["nested"]["api_key"] == "***REDACTED***"
    assert redacted["nested"]["device_id"] == "D1"
