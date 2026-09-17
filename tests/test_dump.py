from bot import parse_dump_command


def test_parse_dump_command():
    assert parse_dump_command(".dump") == {"limit": None}
    assert parse_dump_command(".DUMP") == {"limit": None}
    assert parse_dump_command(".dump 50") == {"limit": 50}
    assert parse_dump_command(".export 100") == {"limit": 100}
    assert parse_dump_command(".export") == {"limit": None}
    assert parse_dump_command(".other") is None
    assert parse_dump_command("") is None
    assert parse_dump_command(None) is None
