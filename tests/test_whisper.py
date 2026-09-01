from bot import parse_whisper_query, WHISPER_HELP


def test_whisper_help_for_empty_query():
    assert parse_whisper_query("") == (None, WHISPER_HELP)


def test_whisper_parses_username_and_text():
    assert parse_whisper_query("@Alice Привет") == ("alice", "Привет")


def test_whisper_requires_username_and_text():
    assert parse_whisper_query("Alice Привет")[0] is None
    assert parse_whisper_query("@Alice")[0] is None
    assert parse_whisper_query("@Alice   ")[0] is None


def test_whisper_rejects_invalid_username():
    assert parse_whisper_query("@bad-name Привет")[0] is None
