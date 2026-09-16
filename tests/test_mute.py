from types import SimpleNamespace

from bot import parse_mute_command, should_delete_for_mute


def test_mute_command_is_recognized():
    assert parse_mute_command('.mute') == 'mute'
    assert parse_mute_command('.unmute') == 'unmute'
    assert parse_mute_command('.ummute') == 'unmute'
    assert parse_mute_command('  .UMMUTE  ') == 'unmute'


def test_command_is_case_insensitive_and_ignores_spaces():
    assert parse_mute_command('  .MUTE  ') == 'mute'
    assert parse_mute_command('.mute now') is None


def test_muted_chat_deletes_non_owner_messages():
    message = SimpleNamespace(from_user=SimpleNamespace(id=42))
    assert should_delete_for_mute(message, owner_id=99, muted=True) is True


def test_muted_chat_keeps_owner_messages():
    message = SimpleNamespace(from_user=SimpleNamespace(id=99))
    assert should_delete_for_mute(message, owner_id=99, muted=True) is False


def test_unmuted_chat_keeps_messages():
    message = SimpleNamespace(from_user=SimpleNamespace(id=42))
    assert should_delete_for_mute(message, owner_id=99, muted=False) is False
