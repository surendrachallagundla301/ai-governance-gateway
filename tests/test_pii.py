from governance_gateway.pii import find_pii, redact


def test_redacts_common_personal_data_and_secrets():
    text = (
        "Contact dana@example.com or (415) 555-0134, SSN 123-45-6789, card 4111 1111 1111 1111, "
        "key AKIAABCDEFGHIJKLMNOP from 10.0.0.12"
    )
    redacted, findings = redact(text)
    kinds = {f.kind for f in findings}
    assert kinds == {"EMAIL", "US_PHONE", "US_SSN", "CREDIT_CARD", "AWS_ACCESS_KEY", "IP_ADDRESS"}
    for secret in ["dana@example.com", "123-45-6789", "4111 1111 1111 1111", "AKIAABCDEFGHIJKLMNOP"]:
        assert secret not in redacted


def test_card_numbers_must_pass_luhn():
    assert not [f for f in find_pii("order 1234 5678 9012 3456") if f.kind == "CREDIT_CARD"]


def test_clean_text_is_unchanged():
    text = "Reset MFA from the security portal."
    assert redact(text) == (text, [])
