import html
import base64
import asyncio
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
        photos = await bot.get_user_profile_photos(user_id=target_id, limit=1)
        file_id = None
        if photos and photos.total_count > 0:
            file_id = photos.photos[0][0].file_id

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


async def download_media_base64(bot: Bot, file_id: str, media_type: str | None) -> tuple[str, str] | None:
    """
    Скачивает медиафайл по file_id и возвращает (base64_content, mime_type).
    Ограничение по размеру: до 20 МБ (максимум для Telegram Bot API).
    """
    if not file_id:
        return None
    try:
        file_info = await bot.get_file(file_id)
        if not file_info.file_path:
            return None

        # Проверка размера (до 20 МБ — лимит Telegram Bot API)
        if file_info.file_size and file_info.file_size > 20 * 1024 * 1024:
            logger.warning(f"Медиа {file_id} слишком большое ({file_info.file_size} байт), пропуск")
            return None

        dest = BytesIO()
        await bot.download_file(file_info.file_path, destination=dest)
        b64_str = base64.b64encode(dest.getvalue()).decode("utf-8")

        # Определение MIME-типа
        if media_type in ("voice", "audio"):
            mime = "audio/ogg"
        elif media_type == "photo":
            mime = "image/jpeg"
        elif media_type in ("video", "video_note", "animation"):
            mime = "video/mp4"
        elif media_type == "sticker":
            mime = "image/webp"
        else:
            mime = "application/octet-stream"

        return b64_str, mime
    except Exception as exc:
        logger.warning(f"Не удалось скачать медиа {file_id} ({media_type}): {exc}")
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
    media_map: dict[str, tuple[str, str]] | None = None,
    is_chat_cleared: bool = False,
) -> str:
    """
    Генерирует автономный HTML-архив в точной стилистике Telegram Desktop Light Theme
    со встроенными воспроизводимыми голосовыми сообщениями и фотографиями.
    """
    media_map = media_map or {}
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
        file_id = msg["file_id"]
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

        content_parts = []
        if badges_html:
            content_parts.append("".join(badges_html))

        # Real Media Rendering
        media_data = media_map.get(file_id) if file_id else None

        if media_type == "voice" or media_type == "audio":
            if media_data:
                b64_val, mime_val = media_data
                audio_id = f"aud_{msg['msg_id']}"
                btn_bg = "#4fae4e" if is_out else "#2481cc"
                content_parts.append(f"""
                    <div class="voice-card">
                        <div class="play-btn" style="background:{btn_bg};" onclick="togglePlay(this, '{audio_id}')">
                            <svg class="icon-play" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                            <svg class="icon-pause" style="display:none;" viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16" fill="white"></rect><rect x="14" y="4" width="4" height="16" fill="white"></rect></svg>
                        </div>
                        <audio id="{audio_id}" src="data:{mime_val};base64,{b64_val}" preload="metadata" onended="onAudioEnded(this)"></audio>
                        <div class="voice-meta">
                            <div class="waveform" id="wave_{audio_id}">
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
                                <span class="wave-bar" style="height: 5px;"></span>
                                <span class="wave-bar" style="height: 14px;"></span>
                                <span class="wave-bar" style="height: 11px;"></span>
                                <span class="wave-bar" style="height: 16px;"></span>
                            </div>
                            <div class="voice-dur" id="dur_{audio_id}">▶ Нажмите чтобы слушать голосовое</div>
                        </div>
                    </div>
                """)
            else:
                content_parts.append("""
                    <div class="voice-card">
                        <div class="play-btn"><svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg></div>
                        <div class="voice-meta"><div class="voice-dur">🎤 Голосовое сообщение</div></div>
                    </div>
                """)
        elif media_type == "photo":
            if media_data:
                b64_val, mime_val = media_data
                content_parts.append(f"""
                    <div class="photo-box">
                        <img class="tg-photo-img" src="data:{mime_val};base64,{b64_val}" alt="Фотография" onclick="openModal(this.src)">
                    </div>
                """)
            else:
                content_parts.append("""
                    <div style="display:flex;align-items:center;gap:8px;padding:4px 0;">
                        <div style="font-size:22px;">📸</div>
                        <div><b>Фотография</b></div>
                    </div>
                """)
        elif media_type == "video_note":
            if media_data:
                b64_val, mime_val = media_data
                vn_id = f"vn_{msg['msg_id']}"
                content_parts.append(f"""
                    <div class="video-note-box" onclick="toggleVideoNote(this, '{vn_id}')">
                        <video id="{vn_id}" class="video-note-media" loop playsinline preload="auto" src="data:{mime_val};base64,{b64_val}" onended="onVideoNoteEnded(this)"></video>
                        <div class="vn-overlay">
                            <div class="vn-play-icon">
                                <svg viewBox="0 0 24 24" width="28" height="28" fill="white"><polygon points="7 4 20 12 7 20 7 4"></polygon></svg>
                            </div>
                        </div>
                        <div class="vn-badge">Кружочек</div>
                    </div>
                """)
            else:
                content_parts.append("""
                    <div class="media-card-stub">
                        <div class="media-stub-icon" style="background:#2b5278;">
                            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="white" stroke-width="2"><circle cx="12" cy="12" r="9"></circle><polygon points="10 8 16 12 10 16 10 8" fill="white"></polygon></svg>
                        </div>
                        <div class="media-stub-meta">
                            <span class="media-stub-title">Видеосообщение (кружочек)</span>
                            <span class="media-stub-desc">Медиафайл недоступен или &gt; 20 МБ</span>
                        </div>
                    </div>
                """)
        elif media_type == "video":
            if media_data:
                b64_val, mime_val = media_data
                content_parts.append(f"""
                    <div class="video-box">
                        <video controls playsinline preload="metadata" src="data:{mime_val};base64,{b64_val}"></video>
                    </div>
                """)
            else:
                content_parts.append("""
                    <div class="media-card-stub">
                        <div class="media-stub-icon" style="background:#2481cc;">
                            <svg viewBox="0 0 24 24" width="22" height="22" fill="white"><path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/></svg>
                        </div>
                        <div class="media-stub-meta">
                            <span class="media-stub-title">Видеозапись</span>
                            <span class="media-stub-desc">Медиафайл недоступен или &gt; 20 МБ</span>
                        </div>
                    </div>
                """)
        elif media_type == "animation":
            if media_data:
                b64_val, mime_val = media_data
                content_parts.append(f"""
                    <div class="anim-box">
                        <video autoplay loop muted playsinline src="data:{mime_val};base64,{b64_val}"></video>
                    </div>
                """)
            else:
                content_parts.append("""
                    <div class="media-card-stub">
                        <div class="media-stub-icon" style="background:#7b68ee;">
                            <svg viewBox="0 0 24 24" width="22" height="22" fill="white"><path d="M19 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm-8 7H9.5v-.5h-2v3h2V13H11v1.5a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1V11zm2.5 4H12V9h1.5v6zm4.5-4.5H16v1.5h1.5V13H16v2h-1.5V9H18v1.5z"/></svg>
                        </div>
                        <div class="media-stub-meta">
                            <span class="media-stub-title">GIF-анимация</span>
                            <span class="media-stub-desc">Медиафайл недоступен или &gt; 20 МБ</span>
                        </div>
                    </div>
                """)
        elif media_type == "document":
            doc_name = html.escape(caption or "Документ")
            content_parts.append(f"""
                <div class="doc-card">
                    <div class="doc-icon-btn"><svg viewBox="0 0 24 24"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"></path></svg></div>
                    <div class="doc-info">
                        <span class="doc-name">{doc_name}</span>
                        <span class="doc-size">Файл</span>
                    </div>
                </div>
            """)
        elif media_type == "sticker":
            if media_data:
                b64_val, mime_val = media_data
                content_parts.append(f"""
                    <div style="margin:4px 0;">
                        <img src="data:{mime_val};base64,{b64_val}" alt="Стикер" style="max-width:160px;max-height:160px;display:block;">
                    </div>
                """)
            else:
                content_parts.append("""
                    <div class="media-card-stub">
                        <div class="media-stub-icon" style="background:#ff9800;font-size:22px;">🎭</div>
                        <div class="media-stub-meta">
                            <span class="media-stub-title">Стикер</span>
                            <span class="media-stub-desc">Стикер Telegram (пропущен)</span>
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

        if caption and media_type != "document":
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

        /* Real Voice Player */
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
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            cursor: pointer;
            box-shadow: 0 1px 3px rgba(0,0,0,0.15);
            flex-shrink: 0;
            transition: transform 0.1s, opacity 0.1s;
        }}
        .play-btn:active {{
            transform: scale(0.95);
        }}
        .play-btn svg {{
            width: 18px;
            height: 18px;
            fill: white;
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
            transition: height 0.1s;
        }}
        .playing .wave-bar {{
            animation: waveBounce 0.6s infinite ease-in-out alternate;
        }}
        .playing .wave-bar:nth-child(2n) {{ animation-delay: 0.15s; }}
        .playing .wave-bar:nth-child(3n) {{ animation-delay: 0.3s; }}
        @keyframes waveBounce {{
            from {{ height: 5px; }}
            to {{ height: 18px; }}
        }}
        .voice-dur {{
            font-size: 12px;
            color: #707579;
        }}

        /* Real Photo Box */
        .photo-box {{
            margin: 4px 0 6px;
            border-radius: 8px;
            overflow: hidden;
            max-width: 420px;
        }}
        .tg-photo-img {{
            width: 100%;
            height: auto;
            max-height: 400px;
            object-fit: cover;
            border-radius: 8px;
            display: block;
            cursor: pointer;
            transition: opacity 0.15s;
        }}
        .tg-photo-img:hover {{
            opacity: 0.94;
        }}

        /* Real Video Note (Кружочек) */
        .video-note-box {{
            width: 240px;
            height: 240px;
            border-radius: 50%;
            overflow: hidden;
            position: relative;
            cursor: pointer;
            display: inline-block;
            background: #000;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
            margin: 4px 0 6px;
            user-select: none;
            -webkit-mask-image: -webkit-radial-gradient(white, black);
        }}
        .video-note-media {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }}
        .vn-overlay {{
            position: absolute;
            inset: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(0, 0, 0, 0.25);
            transition: background 0.2s, opacity 0.2s;
        }}
        .video-note-box:hover .vn-overlay {{
            background: rgba(0, 0, 0, 0.15);
        }}
        .vn-play-icon {{
            width: 54px;
            height: 54px;
            border-radius: 50%;
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.35);
            transition: transform 0.15s;
        }}
        .video-note-box:hover .vn-play-icon {{
            transform: scale(1.08);
        }}
        .vn-play-icon svg {{
            margin-left: 3px;
        }}
        .vn-badge {{
            position: absolute;
            bottom: 12px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(4px);
            color: #fff;
            font-size: 10px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 10px;
            pointer-events: none;
            letter-spacing: 0.3px;
            text-transform: uppercase;
        }}

        /* Real Video Box */
        .video-box {{
            margin: 4px 0 6px;
            max-width: 440px;
            border-radius: 8px;
            overflow: hidden;
            background: #000;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
        }}
        .video-box video {{
            width: 100%;
            max-height: 420px;
            display: block;
            border-radius: 8px;
        }}

        /* Animation / GIF */
        .anim-box {{
            margin: 4px 0 6px;
            max-width: 380px;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
        }}
        .anim-box video {{
            width: 100%;
            max-height: 380px;
            display: block;
            border-radius: 8px;
        }}

        /* Media Fallback Cards */
        .media-card-stub {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 4px 0;
        }}
        .media-stub-icon {{
            width: 44px;
            height: 44px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            flex-shrink: 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.15);
        }}
        .media-stub-meta {{
            display: flex;
            flex-direction: column;
            gap: 2px;
        }}
        .media-stub-title {{
            font-weight: 600;
            font-size: 14px;
            color: #000;
        }}
        .media-stub-desc {{
            font-size: 11.5px;
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
            box-shadow: 0 1px 3px rgba(0,0,0,0.15);
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

        /* Fullscreen Photo Modal */
        #imgModal {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.88);
            z-index: 9999;
            align-items: center;
            justify-content: center;
            cursor: pointer;
        }}
        #imgModal img {{
            max-width: 90vw;
            max-height: 90vh;
            border-radius: 8px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.5);
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

    <!-- Image Modal -->
    <div id="imgModal" onclick="closeModal()">
        <img id="modalImg" src="" alt="Full view">
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

        function togglePlay(btn, audioId) {{
            const audio = document.getElementById(audioId);
            const playIcon = btn.querySelector(".icon-play");
            const pauseIcon = btn.querySelector(".icon-pause");
            const wave = document.getElementById("wave_" + audioId);
            const dur = document.getElementById("dur_" + audioId);

            if (audio.paused) {{
                // Pause all other playing media
                document.querySelectorAll("audio, video").forEach(a => {{
                    if (a !== audio && !a.paused) {{
                        a.pause();
                        const pBox = a.closest(".video-note-box");
                        if (pBox) {{
                            const ov = pBox.querySelector(".vn-overlay");
                            if (ov) ov.style.display = "flex";
                        }}
                        const pBtn = a.parentElement ? a.parentElement.querySelector(".play-btn") : null;
                        if (pBtn) {{
                            pBtn.querySelector(".icon-play").style.display = "block";
                            pBtn.querySelector(".icon-pause").style.display = "none";
                        }}
                        const pWave = document.getElementById("wave_" + a.id);
                        if (pWave) pWave.classList.remove("playing");
                    }}
                }});

                audio.play();
                playIcon.style.display = "none";
                pauseIcon.style.display = "block";
                if (wave) wave.classList.add("playing");
                if (dur) dur.innerText = "Воспроизведение...";

                audio.ontimeupdate = function() {{
                    if (dur && audio.duration) {{
                        const cur = Math.floor(audio.currentTime);
                        const tot = Math.floor(audio.duration);
                        const curM = String(Math.floor(cur / 60)).padStart(2, "0");
                        const curS = String(cur % 60).padStart(2, "0");
                        const totM = String(Math.floor(tot / 60)).padStart(2, "0");
                        const totS = String(tot % 60).padStart(2, "0");
                        dur.innerText = curM + ":" + curS + " / " + totM + ":" + totS;
                    }}
                }};
            }} else {{
                audio.pause();
                playIcon.style.display = "block";
                pauseIcon.style.display = "none";
                if (wave) wave.classList.remove("playing");
                if (dur) dur.innerText = "Пауза";
            }}
        }}

        function onAudioEnded(audio) {{
            const btn = audio.parentElement.querySelector(".play-btn");
            if (btn) {{
                btn.querySelector(".icon-play").style.display = "block";
                btn.querySelector(".icon-pause").style.display = "none";
            }}
            const wave = document.getElementById("wave_" + audio.id);
            if (wave) wave.classList.remove("playing");
            const dur = document.getElementById("dur_" + audio.id);
            if (dur) dur.innerText = "Воспроизведение завершено";
        }}

        function toggleVideoNote(box, vidId) {{
            const v = document.getElementById(vidId);
            const overlay = box.querySelector(".vn-overlay");
            if (!v) return;

            if (v.paused) {{
                // Pause all other playing media
                document.querySelectorAll("video, audio").forEach(el => {{
                    if (el !== v && !el.paused) {{
                        el.pause();
                        const pBox = el.closest(".video-note-box");
                        if (pBox) {{
                            const ov = pBox.querySelector(".vn-overlay");
                            if (ov) ov.style.display = "flex";
                        }}
                        const pBtn = el.parentElement ? el.parentElement.querySelector(".play-btn") : null;
                        if (pBtn) {{
                            pBtn.querySelector(".icon-play").style.display = "block";
                            pBtn.querySelector(".icon-pause").style.display = "none";
                        }}
                        const pWave = document.getElementById("wave_" + el.id);
                        if (pWave) pWave.classList.remove("playing");
                    }}
                }});

                v.play();
                if (overlay) overlay.style.display = "none";
            }} else {{
                v.pause();
                if (overlay) overlay.style.display = "flex";
            }}
        }}

        function onVideoNoteEnded(v) {{
            const box = v.closest(".video-note-box");
            if (box) {{
                const overlay = box.querySelector(".vn-overlay");
                if (overlay) overlay.style.display = "flex";
            }}
        }}

        function openModal(src) {{
            document.getElementById("modalImg").src = src;
            document.getElementById("imgModal").style.display = "flex";
        }}

        function closeModal() {{
            document.getElementById("imgModal").style.display = "none";
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
    user_id: int | None = None,
    included_media_types: set[str] | list[str] | None = None,
):
    """Выгружает все сообщения из базы, собирает HTML-файл и отправляет в ЛС владельцу."""
    messages = await db.get_all_chat_messages(chat_id, limit, user_id=user_id)
    if not messages:
        await bot.send_message(
            owner_chat_id,
            f"ℹ️ В базе данных пока нет сохраненных сообщений для чата <code>{chat_id}</code>."
        )
        return False

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

    # Скачиваем реальные медиафайлы сообщений согласно фильтру
    allowed_types = set(included_media_types) if included_media_types is not None else {"voice", "audio", "photo", "video", "video_note", "animation", "sticker"}

    media_map = {}
    media_tasks = []
    task_keys = []
    sem = asyncio.Semaphore(8)

    async def _download_safe(target_fid: str, target_mtype: str):
        async with sem:
            return await download_media_base64(bot, target_fid, target_mtype)

    for m in messages:
        fid = m["file_id"]
        mtype = m["media_type"]
        if fid and mtype in allowed_types and fid not in media_map:
            media_tasks.append(_download_safe(fid, mtype))
            task_keys.append(fid)

    if media_tasks:
        results = await asyncio.gather(*media_tasks, return_exceptions=True)
        for fid, res in zip(task_keys, results):
            if res and not isinstance(res, Exception):
                media_map[fid] = res

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
        media_map=media_map,
        is_chat_cleared=is_chat_cleared,
    )

    clean_name = target_username or str(chat_id)
    caption_title = "🚨 <b>ЧАТ БЫЛ ОЧИЩЕН СОБЕСЕДНИКОМ!</b>\n\n" if is_chat_cleared else "📦 <b>Экспорт диалога (Telegram Desktop)</b>\n\n"
    caption = (
        f"{caption_title}"
        f"👤 <b>Собеседник:</b> {target_name} (<code>{chat_id}</code>)\n"
        f"💬 <b>Сообщений в архиве:</b> {len(messages)}\n"
        f"🎬 <b>Медиа встроено:</b> {len(media_map)} шт. (кружочки, видео, фото, голос)\n"
        f"🕒 <b>Дата выгрузки:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"<i>Откройте файл на телефоне или ПК — вы сможете смотреть видео, кружочки, фото и слушать голосовые прямо в переписке!</i>"
    )

    doc = BufferedInputFile(html_data.encode("utf-8"), filename=f"chat_dump_{clean_name}.html")
    await bot.send_document(owner_chat_id, document=doc, caption=caption)
    logger.info(f"✅ Дамп чата {chat_id} успешно сформирован с медиа и отправлен владельцу ({owner_chat_id})")
    return True
