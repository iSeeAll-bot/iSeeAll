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


def test_generate_chat_dump_html_media():
    from dump_generator import generate_chat_dump_html

    messages = [
        {
            "msg_id": 1,
            "date": "2026-09-17T10:00:00",
            "sender_id": 123,
            "sender_name": "Alice",
            "sender_username": "alice",
            "media_type": "video_note",
            "file_id": "file_vn_1",
            "text": None,
            "caption": None,
            "is_deleted": 0,
            "delete_date": None,
            "old_text": None,
        },
        {
            "msg_id": 2,
            "date": "2026-09-17T10:01:00",
            "sender_id": 123,
            "sender_name": "Alice",
            "sender_username": "alice",
            "media_type": "video",
            "file_id": "file_vid_1",
            "text": None,
            "caption": "Cool video",
            "is_deleted": 0,
            "delete_date": None,
            "old_text": None,
        },
        {
            "msg_id": 3,
            "date": "2026-09-17T10:02:00",
            "sender_id": 123,
            "sender_name": "Alice",
            "sender_username": "alice",
            "media_type": "animation",
            "file_id": "file_anim_1",
            "text": None,
            "caption": None,
            "is_deleted": 0,
            "delete_date": None,
            "old_text": None,
        },
        {
            "msg_id": 4,
            "date": "2026-09-17T10:03:00",
            "sender_id": 123,
            "sender_name": "Alice",
            "sender_username": "alice",
            "media_type": "video_note",
            "file_id": "file_vn_missing",
            "text": None,
            "caption": None,
            "is_deleted": 0,
            "delete_date": None,
            "old_text": None,
        },
    ]

    media_map = {
        "file_vn_1": ("fake_b64_vn", "video/mp4"),
        "file_vid_1": ("fake_b64_vid", "video/mp4"),
        "file_anim_1": ("fake_b64_anim", "video/mp4"),
    }

    html = generate_chat_dump_html(
        messages=messages,
        interlocutor_name="Alice",
        interlocutor_username="alice",
        interlocutor_id=123,
        interlocutor_avatar_b64=None,
        owner_name="Bob",
        owner_username="bob",
        owner_id=999,
        owner_avatar_b64=None,
        media_map=media_map,
        is_chat_cleared=False,
    )

    # Check video_note rendering with real circular player
    assert "video-note-box" in html
    assert "fake_b64_vn" in html
    assert "toggleVideoNote" in html
    assert "Кружочек" in html

    # Check video rendering with controls
    assert "video-box" in html
    assert "fake_b64_vid" in html
    assert "Cool video" in html

    # Check animation rendering
    assert "anim-box" in html
    assert "fake_b64_anim" in html

    # Check missing media note fallback stub
    assert "media-card-stub" in html
    assert "Видеосообщение (кружочек)" in html


