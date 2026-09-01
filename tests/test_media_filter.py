from types import SimpleNamespace

from bot import is_restricted_media


def media_message(**kwargs):
    values = {
        "photo": [object()],
        "video": None,
        "video_note": None,
        "voice": None,
        "audio": None,
        "document": None,
        "animation": None,
        "sticker": None,
        "has_protected_content": None,
        "model_extra": {},
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_normal_photo_is_not_restricted():
    assert is_restricted_media(media_message()) is False


def test_protected_photo_is_restricted():
    assert is_restricted_media(media_message(has_protected_content=True)) is True


def test_ephemeral_photo_is_restricted():
    assert is_restricted_media(media_message(ephemeral_message_id=77)) is True


def test_protected_video_is_restricted():
    assert is_restricted_media(media_message(photo=None, video=object(), has_protected_content=True)) is True


def test_protected_video_note_is_restricted():
    assert is_restricted_media(media_message(photo=None, video_note=object(), has_protected_content=True)) is True


def test_protected_voice_is_restricted():
    assert is_restricted_media(media_message(photo=None, voice=object(), has_protected_content=True)) is True


def test_protected_document_is_restricted():
    assert is_restricted_media(media_message(photo=None, document=object(), has_protected_content=True)) is True


def test_ttl_video_is_restricted():
    assert is_restricted_media(media_message(photo=None, video=SimpleNamespace(ttl_seconds=30))) is True


def test_raw_ttl_metadata_is_restricted():
    assert is_restricted_media(media_message(photo=None, video=object(), model_extra={"ttl_seconds": 30})) is True


def test_other_media_is_not_intercepted():
    assert is_restricted_media(media_message(photo=None, document=object())) is False
