from bot import whisper_access_allowed


def test_sender_can_open_whisper():
    secret = {"sender_id": 10, "target_username": "alice"}
    assert whisper_access_allowed(secret, user_id=10, username=None) is True


def test_recipient_can_open_whisper():
    secret = {"sender_id": 10, "target_username": "alice"}
    assert whisper_access_allowed(secret, user_id=20, username="Alice") is True


def test_other_user_cannot_open_whisper():
    secret = {"sender_id": 10, "target_username": "alice"}
    assert whisper_access_allowed(secret, user_id=30, username="bob") is False
