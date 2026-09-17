import html
import base64
import logging
from io import BytesIO
from datetime import datetime
from aiogram import Bot
from aiogram.types import BufferedInputFile
import database as db

logger = logging.getLogger("iSeeAllDumpGenerator")


async def get_avatar_base64(bot: Bot, target_id: int) -> str | None:
    """Пытается скачать аватарку пользователя и вернуть её в формате base64."""
    try:
        # Сначала пробуем через get_user_profile_photos
        photos = await bot.get_user_profile_photos(user_id=target_id, limit=1)
        file_id = None
        if photos and photos.total_count > 0:
            file_id = photos.photos[0][0].file_id

        # Если не вышло, пробуем через get_chat
        if not file_id:
            chat = await bot.get_chat(target_id)
            if chat.photo:
                file_id = chat.photo.small_file_id

        if file_id:
            file_info = await bot.get_file(file_id)
            if file_info.file_path:
                dest = BytesIO()
                await bot.download_file(file_info.file_path, destination=dest)
                return base64.b64encode(dest.getvalue()).decode("utf-8")
    except Exception as exc:
        logger.warning(f"Не удалось получить аватарку для {target_id}: {exc}")
    return None


def get_initials(name: str) -> str:
    parts = (name or "").strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    elif parts and parts[0]:
        return parts[0][:2].upper()
    return "TG"


def generate_chat_dump_html(
    messages: list,
    interlocutor_name: str,
    interlocutor_username: str | None,
    interlocutor_id: int,
    interlocutor_avatar_b64: str | None,
    owner_name: str,
    owner_username: str | None,
    owner_id: int,
    owner_avatar_b64: str | None,
    is_chat_cleared: bool = False,
) -> str:
    """
    Генерирует автономный HTML-архив в точном стиле Telegram Desktop Light Theme (1-в-1 по скриншоту).
    """
    safe_target_name = html.escape(interlocutor_name or f"Пользователь {interlocutor_id}")
    safe_target_user = f"@{interlocutor_username}" if interlocutor_username else f"ID: {interlocutor_id}"
    safe_owner_name = html.escape(owner_name or f"ID {owner_id}")
    safe_owner_user = f"@{owner_username}" if owner_username else f"ID: {owner_id}"

    # Owner avatar HTML
    if owner_avatar_b64:
        owner_avatar_img = f'<img src="data:image/jpeg;base64,{owner_avatar_b64}" alt="{safe_owner_name}">'
    else:
        owner_avatar_img = f'<div style="width:24px;height:24px;border-radius:50%;background:#2481cc;color:#fff;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:bold;">{get_initials(owner_name)}</div>'

    # Interlocutor avatar HTML
    if interlocutor_avatar_b64:
        target_avatar_img = f'<img style="width:42px;height:42px;border-radius:50%;object-fit:cover;" src="data:image/jpeg;base64,{interlocutor_avatar_b64}" alt="{safe_target_name}">'
    else:
        target_avatar_img = f'<div style="width:42px;height:42px;border-radius:50%;background:linear-gradient(135deg,#e67e22,#f39c12);display:flex;align-items:center;justify-content:center;font-weight:600;font-size:16px;color:#fff;">{get_initials(interlocutor_name)}</div>'

    # Pinned alert if chat was cleared
    pinned_alert_html = ""
    if is_chat_cleared:
        pinned_alert_html = """
        <div class="alert-banner">
            <div class="alert-left">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                <span>ЧАТ БЫЛ ОЧИЩЕН СОБЕСЕДНИКОМ</span>
            </div>
            <div class="alert-right">История сохранена и зафиксирована базой <b>iSeeAll</b></div>
        </div>
        """

    # Build message rows
    messages_html = []
    last_date_str = None

    for msg in messages:
        msg_date_raw = msg["date"]
        try:
            msg_dt = datetime.fromisoformat(msg_date_raw)
            date_str = msg_dt.strftime("%d %B %Y").replace(
                "January", "января"
            ).replace("February", "февраля").replace("March", "марта").replace(
                "April", "апреля"
            ).replace("May", "мая").replace("June", "июня").replace(
                "July", "июля"
            ).replace("August", "августа").replace("September", "сентября").replace(
                "October", "октября"
            ).replace("November", "ноября").replace("December", "декабря")
            time_str = msg_dt.strftime("%H:%M")
        except Exception:
            date_str = "История переписки"
            time_str = ""

        if date_str != last_date_str:
            messages_html.append(f'<div class="date-badge">{date_str}</div>')
            last_date_str = date_str

        is_out = (msg["sender_id"] == owner_id)
        row_cls = "out" if is_out else "in"
        bubble_cls = "bubble"

        is_deleted = bool(msg["is_deleted"]) if "is_deleted" in msg.keys() else False
        old_text = msg["old_text"] if "old_text" in msg.keys() else None
        media_type = msg["media_type"]
        text = msg["text"]
        caption = msg["caption"]

        badges_html = []
        if is_deleted:
            bubble_cls += " del-bubble"
            del_time = ""
            if "delete_date" in msg.keys() and msg["delete_date"]:
                try:
                    del_time = f" В {datetime.fromisoformat(msg['delete_date']).strftime('%H:%M:%S')}"
                except Exception:
                    pass
            badges_html.append(f"""
                <div class="del-badge">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    <span>УДАЛЕНО СОБЕСЕДНИКОМ{del_time}</span>
                </div>
            """)

        diff_html = ""
        if old_text and old_text != text:
            bubble_cls += " edit-bubble"
            badges_html.append("""
                <div class="edit-badge">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                    <span>ОТРЕДАКТИРОВАНО</span>
                </div>
            """)
            diff_html = f"""
                <div class="edit-diff">
                    <div class="diff-del">❌ Было: {html.escape(old_text)}</div>
                    <div class="diff-add">✅ Стало: {html.escape(text or '')}</div>
                </div>
            """

        # Content rendering
        content_parts = []
        if badges_html:
            content_parts.append("".join(badges_html))

        # Media card rendering
        if media_type == "voice":
            content_parts.append("""
                <div class="voice-card">
                    <div class="play-btn"><svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg></div>
                    <div class="voice-meta">
                        <div class="waveform">
                            <span class="wave-bar" style="height: 6px;"></span>
                            <span class="wave-bar" style="height: 12px;"></span>
                            <span class="wave-bar" style="height: 16px;"></span>
                            <span class="wave-bar" style="height: 8px;"></span>
                            <span class="wave-bar" style="height: 14px;"></span>
                            <span class="wave-bar" style="height: 18px;"></span>
                            <span class="wave-bar" style="height: 10px;"></span>
                            <span class="wave-bar" style="height: 15px;"></span>
                            <span class="wave-bar" style="height: 7px;"></span>
                            <span class="wave-bar" style="height: 13px;"></span>
                        </div>
                        <div class="voice-dur">Голосовое сообщение</div>
                    </div>
                </div>
            """)
        elif media_type == "photo":
            content_parts.append("""
                <div style="display:flex;align-items:center;gap:8px;padding:4px 0;">
                    <div style="font-size:22px;">📸</div>
                    <div><b>Фотография</b></div>
                </div>
            """)
        elif media_type == "document":
            content_parts.append("""
                <div class="doc-card">
                    <div class="doc-icon-btn"><svg viewBox="0 0 24 24"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"></path></svg></div>
                    <div class="doc-info">
                        <span class="doc-name">Документ / Файл</span>
                        <span class="doc-size">Вложение</span>
                    </div>
                </div>
            """)

        # Text and caption
        if text and not diff_html:
            content_parts.append(f"<div>{html.escape(text)}</div>")
        elif text and diff_html:
            content_parts.append(f"<div>{html.escape(text)}</div>{diff_html}")
        elif diff_html:
            content_parts.append(diff_html)

        if caption:
            content_parts.append(f'<div style="margin-top:4px;">{html.escape(caption)}</div>')

        # Checkmarks for out
        checks_html = '<svg class="green-checks" viewBox="0 0 16 16"><path d="M13.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-3.5-3.5a.5.5 0 1 1 .708-.708L6.5 10.293l6.646-6.647a.5.5 0 0 1 .708 0z"/><path d="M10.854 3.646a.5.5 0 0 1 0 .708l-7 7a.5.5 0 0 1-.708 0l-.5-.5a.5.5 0 1 1 .708-.708l.146.147 6.646-6.647a.5.5 0 0 1 .708 0z"/></svg>' if is_out else ""

        body_html = "".join(content_parts)
        search_data = html.escape((text or "") + " " + (caption or "") + " " + (old_text or "")).lower()

        messages_html.append(f"""
        <div class="msg-row {row_cls}" data-text="{search_data}">
            <div class="{bubble_cls}">
                {body_html}
                <div class="time-box">
                    <span>{time_str}</span>
                    {checks_html}
                </div>
            </div>
        </div>
        """)

    all_messages_rendered = "\n".join(messages_html)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_target_name} • Telegram Desktop Export</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            -webkit-font-smoothing: antialiased;
        }}

        body {{
            background: #8aa17a url("https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1920&q=80") center/cover no-repeat fixed;
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            position: relative;
        }}

        body::before {{
            content: "";
            position: absolute;
            inset: 0;
            background: rgba(235, 243, 232, 0.4);
            backdrop-filter: blur(15px);
            z-index: 0;
        }}

        .tg-topbar {{
            background: #ffffff;
            height: 58px;
            border-bottom: 1px solid #e3e3e3;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
            z-index: 10;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            flex-shrink: 0;
        }}

        .topbar-left {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .topbar-info {{
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}

        .topbar-name {{
            font-size: 15.5px;
            font-weight: 600;
            color: #000000;
            line-height: 1.2;
        }}

        .topbar-status {{
            font-size: 13px;
            color: #2481cc;
            font-weight: 400;
        }}

        .topbar-actions {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}

        .owner-chip {{
            display: flex;
            align-items: center;
            gap: 8px;
            background: #f1f3f4;
            padding: 4px 10px 4px 6px;
            border-radius: 20px;
            font-size: 12.5px;
            color: #555;
            border: 1px solid #e0e0e0;
        }}

        .owner-chip img {{
            width: 24px;
            height: 24px;
            border-radius: 50%;
            object-fit: cover;
        }}

        .topbar-icon {{
            cursor: pointer;
            color: #707579;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            transition: background 0.15s;
        }}
        .topbar-icon:hover {{
            background: #f0f2f5;
            color: #000;
        }}

        .search-drawer {{
            background: #ffffff;
            border-bottom: 1px solid #e3e3e3;
            padding: 8px 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            z-index: 9;
        }}

        .search-field {{
            width: 100%;
            background: #f1f3f4;
            border: 1px solid transparent;
            border-radius: 8px;
            padding: 7px 14px 7px 36px;
            font-size: 13.5px;
            outline: none;
            color: #222;
            transition: all 0.2s;
            background-image: url("data:image/svg+xml,%3Csvg xmlns=\x27http://www.w3.org/2000/svg\x27 width=\x2716\x27 height=\x2716\x27 viewBox=\x270 0 24 24\x27 fill=\x27none\x27 stroke=\x27%23707579\x27 stroke-width=\x272\x27 stroke-linecap=\x27round\x27 stroke-linejoin=\x27round\x27%3E%3Ccircle cx=\x2711\x27 cy=\x2711\x27 r=\x278\x27%3E%3C/circle%3E%3Cline x1=\x2721\x27 y1=\x2721\x27 x2=\x2716.65\x27 y2=\x2716.65\x27%3E%3C/line%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: 12px center;
        }}
        .search-field:focus {{
            background: #fff;
            border-color: #2481cc;
            box-shadow: 0 0 0 2px rgba(36, 129, 204, 0.15);
        }}

        .alert-banner {{
            background: #fff5f5;
            border-bottom: 1px solid #fed7d7;
            padding: 8px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 13px;
            z-index: 8;
            border-left: 4px solid #e53e3e;
        }}
        .alert-left {{
            color: #c53030;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .alert-right {{
            color: #742a2a;
            font-size: 12px;
        }}

        .chat-scroll {{
            flex-grow: 1;
            overflow-y: auto;
            padding: 20px 24px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            z-index: 5;
        }}

        .date-badge {{
            align-self: center;
            background: rgba(0, 0, 0, 0.25);
            backdrop-filter: blur(8px);
            color: #ffffff;
            font-size: 12px;
            font-weight: 500;
            padding: 4px 14px;
            border-radius: 14px;
            margin: 10px 0;
            user-select: none;
        }}

        .msg-row {{
            display: flex;
            width: 100%;
            margin-bottom: 4px;
        }}

        .msg-row.in {{
            justify-content: flex-start;
        }}

        .msg-row.out {{
            justify-content: flex-end;
        }}

        .bubble {{
            max-width: 580px;
            min-width: 140px;
            position: relative;
            padding: 7px 12px 6px 14px;
            border-radius: 12px;
            font-size: 14.5px;
            line-height: 1.35;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
            word-wrap: break-word;
        }}

        .in .bubble {{
            background: #ffffff;
            color: #000000;
            border-bottom-left-radius: 3px;
        }}

        .in .bubble::before {{
            content: "";
            position: absolute;
            left: -7px;
            bottom: 0;
            width: 7px;
            height: 12px;
            background: radial-gradient(circle at top left, transparent 7px, #ffffff 7px);
        }}

        .out .bubble {{
            background: #eeffde;
            color: #000000;
            border-bottom-right-radius: 3px;
        }}

        .out .bubble::after {{
            content: "";
            position: absolute;
            right: -7px;
            bottom: 0;
            width: 7px;
            height: 12px;
            background: radial-gradient(circle at top right, transparent 7px, #eeffde 7px);
        }}

        .time-box {{
            float: right;
            display: flex;
            align-items: center;
            gap: 3px;
            margin-left: 12px;
            margin-top: 4px;
            font-size: 11px;
            color: #a0acb6;
            user-select: none;
        }}

        .out .time-box {{
            color: #4fae4e;
        }}

        .green-checks {{
            width: 15px;
            height: 15px;
            fill: #4fae4e;
        }}

        .del-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            background: #fee2e2;
            color: #dc2626;
            border: 1px solid #fca5a5;
            padding: 2px 7px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            margin-bottom: 6px;
        }}
        .del-bubble {{
            border-left: 3px solid #dc2626 !important;
        }}

        .edit-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            background: #fef3c7;
            color: #d97706;
            border: 1px solid #fcd34d;
            padding: 2px 7px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            margin-bottom: 6px;
        }}
        .edit-bubble {{
            border-left: 3px solid #d97706 !important;
        }}

        .edit-diff {{
            background: #fafafa;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 5px 8px;
            margin-top: 5px;
            font-size: 12px;
        }}
        .diff-del {{
            color: #dc2626;
            text-decoration: line-through;
            margin-bottom: 2px;
        }}
        .diff-add {{
            color: #16a34a;
            font-weight: 500;
        }}

        .voice-card {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 4px 0;
        }}
        .play-btn {{
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: #4fae4e;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            flex-shrink: 0;
        }}
        .play-btn svg {{
            width: 18px;
            height: 18px;
            fill: white;
            margin-left: 2px;
        }}
        .voice-meta {{
            display: flex;
            flex-direction: column;
            gap: 3px;
        }}
        .waveform {{
            display: flex;
            align-items: center;
            gap: 2px;
            height: 18px;
        }}
        .wave-bar {{
            width: 3px;
            background: #99c997;
            border-radius: 2px;
        }}
        .voice-dur {{
            font-size: 12px;
            color: #707579;
        }}

        .doc-card {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 4px 0;
        }}
        .doc-icon-btn {{
            width: 44px;
            height: 44px;
            border-radius: 50%;
            background: #2481cc;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            flex-shrink: 0;
        }}
        .doc-icon-btn svg {{
            width: 20px;
            height: 20px;
            fill: white;
        }}
        .doc-info {{
            display: flex;
            flex-direction: column;
        }}
        .doc-name {{
            font-weight: 600;
            font-size: 14px;
            color: #000;
        }}
        .doc-size {{
            font-size: 12px;
            color: #707579;
        }}

        code {{
            background: rgba(0, 0, 0, 0.06);
            border-radius: 3px;
            padding: 1px 4px;
            font-family: monospace;
            font-size: 12.5px;
        }}

        .tg-bottom-bar {{
            background: #ffffff;
            height: 52px;
            border-top: 1px solid #e3e3e3;
            display: flex;
            align-items: center;
            padding: 0 16px;
            gap: 14px;
            z-index: 10;
            box-shadow: 0 -1px 3px rgba(0,0,0,0.04);
            user-select: none;
            flex-shrink: 0;
        }}
        .bottom-icon {{
            color: #707579;
        }}
        .bottom-input-placeholder {{
            flex-grow: 1;
            color: #a2acb4;
            font-size: 14px;
        }}
        .badge-readonly {{
            background: #f0f2f5;
            color: #65676b;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        }}
    </style>
</head>
<body>

    <header class="tg-topbar">
        <div class="topbar-left">
            {target_avatar_img}
            <div class="topbar-info">
                <div class="topbar-name">{safe_target_name}</div>
                <div class="topbar-status">{safe_target_user}</div>
            </div>
        </div>

        <div class="topbar-actions">
            <div class="owner-chip">
                {owner_avatar_img}
                <span>Архив для <b>{safe_owner_name}</b> ({safe_owner_user})</span>
            </div>
            <div class="topbar-icon" title="Поиск">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            </div>
        </div>
    </header>

    {pinned_alert_html}

    <div class="search-drawer">
        <input type="text" id="searchInput" class="search-field" placeholder="Поиск по сообщениям..." oninput="doSearch()">
    </div>

    <main class="chat-scroll" id="messagesArea">
        {all_messages_rendered}
    </main>

    <div class="tg-bottom-bar">
        <div class="bottom-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>
        </div>
        <div class="bottom-input-placeholder">Резервная копия диалога сохранена <b>iSeeAll</b> • Всего сообщений: {len(messages)}</div>
        <div class="badge-readonly">Только чтение</div>
        <div class="bottom-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"></circle><path d="M8 14s1.5 2 4 2 4-2 4-2"></path><line x1="9" y1="9" x2="9.01" y2="9"></line><line x1="15" y1="9" x2="15.01" y2="9"></line></svg>
        </div>
        <div class="bottom-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg>
        </div>
    </div>

    <script>
        function doSearch() {{
            const q = document.getElementById("searchInput").value.toLowerCase().trim();
            const rows = document.querySelectorAll(".msg-row");
            rows.forEach(r => {{
                const txt = r.getAttribute("data-text") || "";
                r.style.display = (!q || txt.includes(q)) ? "flex" : "none";
            }});
        }}
    </script>
</body>
</html>
"""


async def execute_and_send_dump(
    bot: Bot,
    chat_id: int,
    owner_chat_id: int,
    owner_id: int,
    limit: int | None = None,
    is_chat_cleared: bool = False,
):
    """Выгружает все сообщения из базы, собирает HTML-файл и отправляет в ЛС владельцу."""
    messages = await db.get_all_chat_messages(chat_id, limit)
    if not messages:
        await bot.send_message(
            owner_chat_id,
            f"ℹ️ В базе данных пока нет сохраненных сообщений для чата <code>{chat_id}</code>."
        )
        return

    # Получаем данные собеседника
    target_name = None
    target_username = None
    for m in messages:
        if m["sender_id"] and m["sender_id"] != owner_id:
            target_name = m["sender_name"]
            target_username = m["sender_username"]
            break

    try:
        chat = await bot.get_chat(chat_id)
        if chat:
            target_name = chat.first_name or target_name
            target_username = chat.username or target_username
    except Exception:
        pass

    target_name = target_name or f"Пользователь {chat_id}"

    # Получаем аватарки
    interlocutor_b64 = await get_avatar_base64(bot, chat_id)
    owner_b64 = await get_avatar_base64(bot, owner_id)

    # Получаем данные владельца
    owner_name = "Владелец"
    owner_username = None
    try:
        owner_chat = await bot.get_chat(owner_id)
        if owner_chat:
            owner_name = owner_chat.first_name or "Владелец"
            owner_username = owner_chat.username
    except Exception:
        pass

    # Генерация HTML
    html_data = generate_chat_dump_html(
        messages=messages,
        interlocutor_name=target_name,
        interlocutor_username=target_username,
        interlocutor_id=chat_id,
        interlocutor_avatar_b64=interlocutor_b64,
        owner_name=owner_name,
        owner_username=owner_username,
        owner_id=owner_id,
        owner_avatar_b64=owner_b64,
        is_chat_cleared=is_chat_cleared,
    )

    clean_name = target_username or str(chat_id)
    caption_title = "🚨 <b>ЧАТ БЫЛ ОЧИЩЕН СОБЕСЕДНИКОМ!</b>\n\n" if is_chat_cleared else "📦 <b>Экспорт диалога (Telegram Desktop)</b>\n\n"
    caption = (
        f"{caption_title}"
        f"👤 <b>Собеседник:</b> {target_name} (<code>{chat_id}</code>)\n"
        f"💬 <b>Сообщений в архиве:</b> {len(messages)}\n"
        f"🕒 <b>Дата выгрузки:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<i>Откройте прикрепленный HTML-файл на телефоне или ПК для просмотра.</i>"
    )

    doc = BufferedInputFile(html_data.encode("utf-8"), filename=f"chat_dump_{clean_name}.html")
    await bot.send_document(owner_chat_id, document=doc, caption=caption)
    logger.info(f"✅ Дамп чата {chat_id} успешно сформирован и отправлен владельцу ({owner_chat_id})")
