from bot import parse_dump_command, build_dump_keyboard


def test_parse_dump_command():
    assert parse_dump_command(".dump") == {"limit": None}
    assert parse_dump_command(".DUMP") == {"limit": None}
    assert parse_dump_command(".dump 50") == {"limit": 50}
    assert parse_dump_command(".export 100") == {"limit": 100}
    assert parse_dump_command(".export") == {"limit": None}
    assert parse_dump_command(".other") is None
    assert parse_dump_command("") is None
    assert parse_dump_command(None) is None


def test_build_dump_keyboard_single_page():
    chats = [
        {"chat_id": 101, "sender_name": "Alice", "sender_username": "alice", "msg_count": 5},
        {"chat_id": 102, "sender_name": "Bob", "sender_username": None, "msg_count": 12},
    ]
    markup = build_dump_keyboard(chats, page=0, total_chats=2, page_size=5)
    assert len(markup.inline_keyboard) == 3  # 2 chats + 1 close button
    assert "Alice" in markup.inline_keyboard[0][0].text
    assert markup.inline_keyboard[0][0].callback_data == "dump:chat:101"
    assert markup.inline_keyboard[1][0].callback_data == "dump:chat:102"
    assert markup.inline_keyboard[2][0].callback_data == "dump:close"


def test_build_dump_keyboard_pagination():
    chats = [{"chat_id": i, "sender_name": f"User {i}", "sender_username": None, "msg_count": i} for i in range(5)]
    # First page of 2 pages
    markup = build_dump_keyboard(chats, page=0, total_chats=8, page_size=5)
    # 5 chat buttons + 1 nav row + 1 close button = 7 rows
    assert len(markup.inline_keyboard) == 7
    nav_row = markup.inline_keyboard[5]
    assert len(nav_row) == 2  # Page indicator + Next
    assert nav_row[0].text == "📄 1/2"
    assert nav_row[1].callback_data == "dump:page:1"

    # Second page
    markup_p2 = build_dump_keyboard(chats[:3], page=1, total_chats=8, page_size=5)
    assert len(markup_p2.inline_keyboard) == 5  # 3 chats + 1 nav row + 1 close button
    nav_p2 = markup_p2.inline_keyboard[3]
    assert len(nav_p2) == 2  # Prev + Page indicator
    assert nav_p2[0].callback_data == "dump:page:0"
    assert nav_p2[1].text == "📄 2/2"

