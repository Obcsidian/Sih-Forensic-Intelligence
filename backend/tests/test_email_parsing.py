from app.services.email_parsing import format_message_body, parse_eml

RAW_EMAIL = (
    b"From: Alice <alice@example.com>\r\n"
    b"To: Bob <bob@example.com>, carol@example.com\r\n"
    b"Subject: Meeting tonight\r\n"
    b"Date: Thu, 1 Jan 2026 10:00:00 +0000\r\n"
    b"Content-Type: text/plain; charset=\"utf-8\"\r\n"
    b"\r\n"
    b"Let's meet at 9pm at the usual place.\r\n"
)


def test_parse_eml_extracts_headers_and_body():
    parsed = parse_eml(RAW_EMAIL)

    assert parsed is not None
    assert parsed.sender == "alice@example.com"
    assert parsed.recipients == ["bob@example.com", "carol@example.com"]
    assert parsed.subject == "Meeting tonight"
    assert "Let's meet at 9pm" in parsed.body
    assert parsed.sent_at is not None
    assert parsed.sent_at.year == 2026


def test_parse_eml_returns_none_without_from_header():
    assert parse_eml(b"Subject: no sender\r\n\r\nbody") is None


def test_parse_eml_handles_garbage_bytes():
    assert parse_eml(b"\x00\x01\x02not an email") is None


def test_format_message_body_prefixes_subject():
    parsed = parse_eml(RAW_EMAIL)
    formatted = format_message_body(parsed)
    assert formatted.startswith("Subject: Meeting tonight\n\n")
