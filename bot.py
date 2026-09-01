import asyncio
import logging
import html
import secrets
import time
from io import BytesIO
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import (
    BufferedInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from config import BOT_TOKEN, OWNER_ID, CACHE_DAYS, HTTP_PROXY, HTTPS_PROXY, BOT_NAME, REPO_URL
import database as db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("iSeeAllBusinessBot")

proxy_url = HTTPS_PROXY or HTTP_PROXY or None
session = AiohttpSession(proxy=proxy_url) if proxy_url else AiohttpSession()

bot = Bot(
    token=BOT_TOKEN or "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    session=session,
)
dp = Dispatcher()


def fmt_time() -> str:
    return datetime.now().strftime("%d.%m.%Y | %H:%M:%S")


def quote_text(text: str | None) -> str:
    safe_text = html.escape(text or "пусто")
    return f"<blockquote>{safe_text}</blockquote>"


def user_id_line(user_id: int | None) -> str:
    return f"🆔 <b>User ID:</b> <code>{user_id}</code>\n" if user_id else ""


MEDIA_TITLES = {
    "photo": ("📸", "фото"),
    "video": ("🎬", "видео"),
    "animation": ("🎞", "GIF/анимация"),
    "voice": ("🎤", "голосовое сообщение"),
    "video_note": ("⭕️", "видеокружок"),
    "audio": ("🎵", "аудио"),
    "document": ("📎", "документ"),
    "sticker": ("🧩", "стикер"),
}


def media_title(media_type: str | None, action: str) -> str:
    emoji, name = MEDIA_TITLES.get(media_type or "", ("📎", "медиа"))
    if action == "hidden":
        if media_type == "photo":
            return "📸 <b>Перехвачено одноразовое фото</b>"
        if media_type == "video":
            return "🎬 <b>Перехвачено скрытое видео</b>"
        return f"{emoji} <b>Перехвачено скрытое медиа: {name}</b>"
    if action == "deleted":
        if media_type == "voice":
            return "🎤 <b>Удалено голосовое сообщение</b>"
        if media_type == "video_note":
            return "⭕️ <b>Удален видеокружок</b>"
        return f"{emoji} <b>Удалено {name}</b>"
    return f"{emoji} <b>{name}</b>"


def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔌 Как подключить?", callback_data="how_to_connect")],
        [InlineKeyboardButton(text="💻 GitHub", url=REPO_URL)],
    ])


GAMES: dict[int, dict] = {}
WHISPERS: dict[str, dict] = {}
WHISPER_HELP = "🔐 <b>Шептун</b>\n\nВведи: <code>@{bot} @пользователь текст</code>"


def parse_whisper_query(query: str) -> tuple[str | None, str]:
    query = (query or "").strip()
    if not query:
        return None, WHISPER_HELP
    parts = query.split(maxsplit=1)
    if len(parts) != 2 or not parts[0].startswith("@"):
        return None, WHISPER_HELP
    username = parts[0][1:].lower()
    if not username.replace("_", "").isalnum():
        return None, WHISPER_HELP
    text = parts[1].strip()
    if not text:
        return None, WHISPER_HELP
    return username, text


def whisper_help_text(bot_username: str) -> str:
    return WHISPER_HELP.format(bot=html.escape(bot_username.lstrip("@")))


def whisper_access_allowed(secret: dict, user_id: int, username: str | None) -> bool:
    return (
        user_id == secret.get("sender_id")
        or (username or "").lower() == secret.get("target_username")
    )


def whisper_button(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔐 Открыть шепот", callback_data=f"whisper:{token}")
    ]])


def whisper_result_text(target_username: str) -> str:
    return f"🔐 Секретное сообщение для <b>@{html.escape(target_username)}</b>\nНажми кнопку, чтобы открыть его."


def whisper_inline_result(token: str, target_username: str, text: str) -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id=token,
        title=f"Шепот для @{target_username}",
        description="Сообщение увидит только указанный пользователь",
        input_message_content=InputTextMessageContent(
            message_text=whisper_result_text(target_username),
            parse_mode="HTML",
        ),
        reply_markup=whisper_button(token),
    )


def whisper_help_result() -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id="whisper-help",
        title="Как отправить шепот",
        description="@пользователь текст — сообщение увидит только адресат",
        input_message_content=InputTextMessageContent(
            message_text="🔐 <b>Шепот</b>\n\nУкажи пользователя и текст: <code>@username секретное сообщение</code>",
            parse_mode="HTML",
        ),
    )
RPS_CHOICES = {"rock": "✊ Камень", "scissors": "✂️ Ножницы", "paper": "📄 Бумага"}


def new_rps_game(owner_id: int, opponent_id: int, owner_name: str, opponent_name: str) -> dict:
    return {
        "owner_id": owner_id, "opponent_id": opponent_id,
        "kind": "rps",
        "owner_name": owner_name, "opponent_name": opponent_name,
        "owner_choice": None, "opponent_choice": None, "status": "active",
    }


def rps_result(owner_choice: str, opponent_choice: str) -> str:
    if owner_choice == opponent_choice:
        return "draw"
    return "owner" if (owner_choice, opponent_choice) in {
        ("rock", "scissors"), ("scissors", "paper"), ("paper", "rock")
    } else "opponent"


def apply_rps_choice(game: dict, player_id: int, choice: str) -> bool:
    if game.get("status") != "active" or choice not in RPS_CHOICES:
        return False
    if player_id == game["owner_id"]:
        if game["owner_choice"] is not None:
            return False
        game["owner_choice"] = choice
    elif player_id == game["opponent_id"]:
        if game["opponent_choice"] is not None:
            return False
        game["opponent_choice"] = choice
    else:
        return False
    if game["owner_choice"] and game["opponent_choice"]:
        game["status"] = "finished"
    return True


def game_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌⭕ Крестики-нолики", callback_data="game:ttt")],
        [InlineKeyboardButton(text="✊ КНБ", callback_data="game:rps")],
    ])


def rps_keyboard(chat_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✊", callback_data=f"rps:{chat_id}:rock"),
        InlineKeyboardButton(text="✂️", callback_data=f"rps:{chat_id}:scissors"),
        InlineKeyboardButton(text="📄", callback_data=f"rps:{chat_id}:paper"),
    ]])


def new_game(owner_id: int, opponent_id: int, owner_name: str = "Игрок 1", opponent_name: str = "Игрок 2") -> dict:
    return {
        "owner_id": owner_id,
        "opponent_id": opponent_id,
        "kind": "ttt",
        "owner_name": owner_name,
        "opponent_name": opponent_name,
        "board": [" "] * 9,
        "turn": owner_id,
        "status": "active",
        "invited": True,
    }


def game_status(game: dict) -> str:
    board = game["board"]
    for a, b, c in ((0, 1, 2), (3, 4, 5), (6, 7, 8),
                    (0, 3, 6), (1, 4, 7), (2, 5, 8),
                    (0, 4, 8), (2, 4, 6)):
        if board[a] != " " and board[a] == board[b] == board[c]:
            player = game["owner_id"] if board[a] == "X" else game["opponent_id"]
            game["status"] = f"winner:{player}"
            return game["status"]
    if " " not in board:
        game["status"] = "draw"
    return game["status"]


def apply_move(game: dict, index: int, player_id: int) -> bool:
    if game.get("status") != "active" or player_id != game["turn"]:
        return False
    if not isinstance(index, int) or not 0 <= index < 9 or game["board"][index] != " ":
        return False
    game["board"][index] = "X" if player_id == game["owner_id"] else "O"
    game["turn"] = game["opponent_id"] if player_id == game["owner_id"] else game["owner_id"]
    game_status(game)
    return True


def game_keyboard_rows(board: list[str], game_id: int | None = None):
    prefix = f"ttt:{game_id}:" if game_id is not None else "ttt:test:"
    return [
        [InlineKeyboardButton(text=cell if cell != " " else "·", callback_data=f"{prefix}{i}") for i, cell in enumerate(board[row:row + 3], row)]
        for row in (0, 3, 6)
    ]


def invite_keyboard(chat_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Принять", callback_data=f"ttt_accept:{chat_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"ttt_decline:{chat_id}"),
    ]])


def game_invite_text(game: dict) -> str:
    return "🎮 <b>Крестики-нолики</b>\n\nТебе предлагают сыграть. Примешь вызов?"


def game_markup(game: dict, chat_id: int):
    return InlineKeyboardMarkup(inline_keyboard=game_keyboard_rows(game["board"], chat_id))


def render_game(game: dict) -> str:
    status = game_status(game)
    if status == "active":
        turn = game["owner_name"] if game["turn"] == game["owner_id"] else game["opponent_name"]
        footer = f"Ход: <b>{turn}</b>"
    elif status == "draw":
        footer = "🤝 Ничья!"
    else:
        winner = game["owner_name"] if status == f"winner:{game['owner_id']}" else game["opponent_name"]
        footer = f"🏆 Победитель: <b>{winner}</b>"
    cells = game["board"]
    board = "\n".join(
        " | ".join(c if c != " " else "·" for c in cells[row:row + 3])
        for row in (0, 3, 6)
    )
    return "🎮 <b>Крестики-нолики</b>\n\n<code>" + board + "</code>\n\n" + footer


def parse_mute_command(text: str | None) -> str | None:
    command = (text or "").strip().lower()
    return command[1:] if command in {".mute", ".unmute"} else None


def is_game_command(text: str | None) -> bool:
    return (text or "").strip().lower() == ".game"


def parse_spam_command(text: str | None) -> tuple[int, list[str]] | None:
    parts = (text or "").strip().split(maxsplit=2)
    if len(parts) < 3 or parts[0].lower() != ".spam":
        return None
    try:
        count = int(parts[1])
    except ValueError:
        return None
    if not 1 <= count <= 50:
        return None
    variants = [item.strip() for item in parts[2].split(",") if item.strip()]
    return (count, variants) if variants else None


def spam_text_for_index(variants: list[str], index: int) -> str:
    return variants[index % len(variants)]


def should_delete_for_mute(message: types.Message, owner_id: int, muted: bool) -> bool:
    sender_id = message.from_user.id if message.from_user else None
    return muted and sender_id is not None and sender_id != owner_id


async def get_owner_user_id() -> int:
    if OWNER_ID:
        return OWNER_ID
    stored_owner = await db.get_setting("owner_id")
    return int(stored_owner) if stored_owner and stored_owner.isdigit() else 0


async def ensure_owner_user_id(user_id: int) -> int:
    current_owner = await get_owner_user_id()
    if current_owner:
        return current_owner
    await db.set_setting("owner_id", str(user_id))
    return user_id


async def is_owner_user(user_id: int) -> bool:
    return user_id == await get_owner_user_id()


def _positive_ttl(value) -> bool:
    """Возвращает True, если значение TTL задано положительным числом."""
    try:
        return value is not None and int(value) > 0
    except (TypeError, ValueError):
        return False


def _object_value(obj, key: str):
    """Читает поле модели aiogram или сырые поля Telegram."""
    if obj is None:
        return None
    value = getattr(obj, key, None)
    if value is not None:
        return value
    extra = getattr(obj, "model_extra", None) or {}
    return extra.get(key)


def _nested_value(obj, *keys, _seen=None):
    """Ищет признак в aiogram-моделях, model_extra, списках и dict."""
    if obj is None:
        return None
    if _seen is None:
        _seen = set()
    if isinstance(obj, (dict, list, tuple)) or hasattr(obj, "__dict__"):
        marker = id(obj)
        if marker in _seen:
            return None
        _seen.add(marker)

    if isinstance(obj, dict):
        for key in keys:
            if obj.get(key) is not None:
                return obj[key]
        values = obj.values()
    elif isinstance(obj, (list, tuple)):
        values = obj
    else:
        for key in keys:
            value = _object_value(obj, key)
            if value is not None:
                return value
        values = []
        # Обходим все объявленные поля модели и неизвестные raw-поля.
        model_dump = getattr(obj, "model_dump", None)
        if callable(model_dump):
            try:
                dumped = model_dump(exclude_none=True)
                if isinstance(dumped, dict):
                    values.extend(dumped.values())
            except Exception:
                pass
        extra = getattr(obj, "model_extra", None)
        if isinstance(extra, dict):
            values.extend(extra.values())
        raw_dict = getattr(obj, "__dict__", None)
        if isinstance(raw_dict, dict):
            values.extend(raw_dict.values())

    for value in values:
        found = _nested_value(value, *keys, _seen=_seen)
        if found is not None:
            return found
    return None


def _has_restricted_marker(message: types.Message) -> bool:
    """Проверяет TTL/view-once в любом месте сырого Business-апдейта."""
    return (
        _nested_value(message, "ephemeral_message_id") is not None
        or _positive_ttl(_nested_value(message, "ttl_seconds"))
        or any(_nested_value(message, key) is True for key in (
            "has_view_once", "is_view_once", "view_once", "is_secret"
        ))
    )


def is_restricted_media(message: types.Message) -> bool:
    """Определяет ограниченное медиа в Business API."""
    media_fields = (
        "photo", "video", "video_note", "animation", "voice", "audio", "document", "sticker"
    )
    if not any(getattr(message, field, None) for field in media_fields):
        return False

    # В Business API одноразовое/ограниченное медиа приходит с
    # has_protected_content=True, без ttl_seconds.
    if getattr(message, "has_protected_content", False) is True:
        return True

    return _has_restricted_marker(message)


def reply_source_message(message: types.Message):
    """Возвращает сообщение, на которое ответил владелец."""
    return message.reply_to_message or message.external_reply


def extract_media(message: types.Message):
    """
    Извлекает тип медиа, file_id и file_unique_id из сообщения.
    """
    if message.photo:
        return "photo", message.photo[-1].file_id, message.photo[-1].file_unique_id
    elif message.video:
        return "video", message.video.file_id, message.video.file_unique_id
    elif message.animation:
        return "animation", message.animation.file_id, message.animation.file_unique_id
    elif message.voice:
        return "voice", message.voice.file_id, message.voice.file_unique_id
    elif message.video_note:
        return "video_note", message.video_note.file_id, message.video_note.file_unique_id
    elif message.audio:
        return "audio", message.audio.file_id, message.audio.file_unique_id
    elif message.document:
        return "document", message.document.file_id, message.document.file_unique_id
    elif message.sticker:
        return "sticker", message.sticker.file_id, message.sticker.file_unique_id
    return None, None, None


def get_sender_display_name(from_user: types.User | None):
    if not from_user:
        return "Неизвестно"
    name = html.escape(from_user.full_name)
    if from_user.username:
        name += f" (@{html.escape(from_user.username)})"
    return name


async def load_replied_media_to_buffer(file_id: str) -> bytes | None:
    if not file_id:
        return None

    try:
        buffer = BytesIO()
        downloaded = await bot.download(file_id, destination=buffer)
        source = downloaded if downloaded is not None else buffer

        if hasattr(source, "seek"):
            source.seek(0)

        data = source.read() if hasattr(source, "read") else b""
        if not data and hasattr(buffer, "getvalue"):
            data = buffer.getvalue()

        if not data:
            return None

        return data
    except Exception as exc:
        logger.exception(f"Не удалось скачать медиа в память: {exc}")
        return None




@dp.business_connection()
async def on_business_connection(conn: types.BusinessConnection):
    """
    Событие подключения или отключения бизнес-бота от аккаунта пользователя.
    """
    await db.save_connection(
        connection_id=conn.id,
        user_id=conn.user.id,
        user_chat_id=conn.user_chat_id,
        can_reply=conn.can_reply,
        is_enabled=conn.is_enabled
    )
    await db.save_user(
        user_id=conn.user.id,
        chat_id=conn.user_chat_id,
        first_name=conn.user.first_name,
        username=conn.user.username,
    )
    status = "подключен" if conn.is_enabled else "отключен"
    logger.info(f"Бизнес-бот {status} для пользователя {conn.user.full_name} ({conn.user.id})")

    try:
        if conn.is_enabled:
            await bot.send_message(
                conn.user_chat_id,
                f"✅ <b>{BOT_NAME} успешно подключен к вашему бизнес-аккаунту!</b>\n\n"
                f"• Удаленные сообщения будут пересылаться вам сюда.\n"
                f"• Если вам прислали фото/видео с таймером (одноразовое) — просто ответьте на него любым символом (например точкой <code>.</code>), и бот отправит вам его постоянную копию!"
            )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление о подключении: {e}")


@dp.business_message()
async def on_business_message(message: types.Message):
    """
    Обработка сообщений, проходящих через личные чаты привязанного бизнес-аккаунта.
    """
    conn_id = message.business_connection_id
    if not conn_id:
        return

    conn = await db.get_connection(conn_id)
    if not conn or not conn["is_enabled"]:
        logger.warning(
            f"Неизвестное или отключённое бизнес-подключение {conn_id} — сообщение проигнорировано"
        )
        return

    owner_user_id = conn["user_id"]
    owner_chat_id = conn["user_chat_id"]

    # Команда .game приходит как business_message, а не как обычное
    # сообщение боту. Поэтому обрабатываем её здесь — в контексте диалога.
    if is_owner_message := (message.from_user and message.from_user.id == owner_user_id):
        if is_game_command(message.text):
            await message.answer("🎮 <b>Выбери игру</b>", reply_markup=game_menu_keyboard())
            logger.info("🎮 Приглашение в игру отправлено в чат %s", message.chat.id)
            return

        spam_request = parse_spam_command(message.text)
        if spam_request:
            count, variants = spam_request
            for index in range(count):
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=spam_text_for_index(variants, index),
                    business_connection_id=conn_id,
                )
                await asyncio.sleep(0.1)
            logger.info(".spam отправил %s сообщений в чат %s", count, message.chat.id)
            return

    # .mute/.unmute управляют только текущим диалогом. Команда доступна
    # владельцу бизнес-аккаунта и не считается сообщением собеседника.
    command = parse_mute_command(message.text)
    if is_owner_message and command:
        muted = command == "mute"
        await db.set_muted_chat(conn_id, message.chat.id, muted)
        status = "включён" if muted else "выключен"
        await bot.send_message(
            owner_chat_id,
            f"{'🔇' if muted else '🔊'} <b>Мут {status}</b>\n"
            f"Чат: <code>{message.chat.id}</code>"
        )
        return

    # Удаляем любое сообщение собеседника до кэширования или другой обработки.
    if should_delete_for_mute(
        message,
        owner_id=owner_user_id,
        muted=await db.is_chat_muted(conn_id, message.chat.id),
    ):
        try:
            await bot.delete_business_messages(
                business_connection_id=conn_id,
                message_ids=[message.message_id],
            )
            logger.info(
                "🔇 Сообщение %s в чате %s удалено режимом mute",
                message.message_id,
                message.chat.id,
            )
        except Exception as exc:
            logger.error("Не удалось удалить сообщение режима mute: %s", exc)
        return

    # Проверяем, ответил ли владелец на сообщение с медиа
    if is_owner_message and reply_source_message(message):
        replied = reply_source_message(message)

        replied_raw = (
            replied.model_dump(exclude_none=True)
            if hasattr(replied, "model_dump")
            else {}
        )
        logger.info(
            "Reply media probe: reply=%s external=%s source=%s ttl=%r "
            "source_keys=%s source_json=%s",
            bool(message.reply_to_message),
            bool(message.external_reply),
            type(replied).__name__,
            _nested_value(replied, "ttl_seconds"),
            sorted(replied_raw.keys()),
            replied_raw,
        )

        # Перехватываем только фото/видео с TTL/view-once.
        # Ответ на обычное медиа не должен запускать сохранение.
        if not is_restricted_media(replied):
            logger.info("Ответ на обычное медиа проигнорирован как неограниченное")
        else:
            media_type, file_id, _ = extract_media(replied)

            # Если в отвеченном сообщении есть ограниченное медиа, пытаемся
            # скачать его локально и отправить владельцу в ЛС.
            if file_id and media_type and owner_chat_id:
                sender_info = get_sender_display_name(replied.from_user)
                sender_id = replied.from_user.id if replied.from_user else None
                caption = (
                    f"{media_title(media_type, 'hidden')}\n"
                    f"👤 <b>От:</b>     {sender_info}\n"
                    f"{user_id_line(sender_id)}"
                    f"💬 <b>Чат ID:</b> <code>{message.chat.id}</code>\n"
                    f"🕒 <b>Время:</b>  {fmt_time()}\n"
                )
                if replied.caption:
                    caption += f"\n📝 <b>Подпись:</b>\n{quote_text(replied.caption)}\n"

                try:
                    data = await load_replied_media_to_buffer(file_id)

                    if data:
                        if media_type == "photo":
                            await bot.send_photo(owner_chat_id, photo=BufferedInputFile(data, filename="photo.jpg"), caption=caption)
                        elif media_type == "video":
                            await bot.send_video(owner_chat_id, video=BufferedInputFile(data, filename="video.mp4"), caption=caption)
                        elif media_type == "animation":
                            await bot.send_animation(owner_chat_id, animation=BufferedInputFile(data, filename="animation.mp4"), caption=caption)
                        elif media_type == "voice":
                            await bot.send_voice(owner_chat_id, voice=BufferedInputFile(data, filename="voice.ogg"), caption=caption)
                        elif media_type == "video_note":
                            await bot.send_video_note(owner_chat_id, video_note=BufferedInputFile(data, filename="video_note.mp4"))
                            await bot.send_message(owner_chat_id, caption)
                        elif media_type == "audio":
                            await bot.send_audio(owner_chat_id, audio=BufferedInputFile(data, filename="audio.mp3"), caption=caption)
                        elif media_type == "document":
                            await bot.send_document(owner_chat_id, document=BufferedInputFile(data, filename="document.bin"), caption=caption)
                        elif media_type == "sticker":
                            await bot.send_sticker(owner_chat_id, sticker=file_id)
                            await bot.send_message(owner_chat_id, caption)
                        else:
                            await bot.send_message(owner_chat_id, caption)

                        logger.info(f"💾 Медиа ({media_type}) отправлено владельцу из памяти")
                    else:
                        await bot.send_message(owner_chat_id, caption + "\n\n<code>Не удалось скачать файл в память.</code>")
                except Exception as e:
                    logger.error(f"Не удалось отправить медиа по реплаю: {e}")

    # Кэшируем сообщение в базе данных
    media_type, file_id, file_unique_id = extract_media(message)
    sender_name = get_sender_display_name(message.from_user)
    sender_username = message.from_user.username if message.from_user else None

    await db.save_message(
        connection_id=conn_id,
        msg_id=message.message_id,
        chat_id=message.chat.id,
        sender_id=message.from_user.id if message.from_user else None,
        sender_name=sender_name,
        sender_username=sender_username,
        text=message.text,
        media_type=media_type,
        file_id=file_id,
        file_unique_id=file_unique_id,
        caption=message.caption
    )




@dp.edited_business_message()
async def on_edited_business_message(message: types.Message):
    """
    Логирует изменения сообщений в подключенном бизнес-чате.
    """
    conn_id = message.business_connection_id
    if not conn_id:
        return

    conn = await db.get_connection(conn_id)
    if not conn or not conn["is_enabled"]:
        logger.warning(
            f"Неизвестное или отключённое бизнес-подключение {conn_id} — изменение проигнорировано"
        )
        return

    owner_user_id = conn["user_id"]
    owner_chat_id = conn["user_chat_id"]

    old_record = await db.get_message(conn_id, message.chat.id, message.message_id)
    media_type, file_id, file_unique_id = extract_media(message)
    sender_name = get_sender_display_name(message.from_user)
    sender_username = message.from_user.username if message.from_user else None
    new_text = message.text or ""
    new_caption = message.caption or ""

    if old_record:
        old_text = old_record["text"] or ""
        old_caption = old_record["caption"] or ""
        old_media_type = old_record["media_type"] or ""
    else:
        old_text = ""
        old_caption = ""
        old_media_type = ""

    changed_parts = []
    if old_text != new_text:
        changed_parts.append(
            f"❌ <b>Было:</b>\n{quote_text(old_text)}\n"
            f"✅ <b>Стало:</b>\n{quote_text(new_text)}"
        )
    if old_caption != new_caption:
        changed_parts.append(
            f"❌ <b>Подпись была:</b>\n{quote_text(old_caption)}\n"
            f"✅ <b>Подпись стала:</b>\n{quote_text(new_caption)}"
        )
    if old_media_type != (media_type or ""):
        changed_parts.append(
            f"<b>Медиа было:</b> <code>{old_media_type or 'нет'}</code>\n"
            f"<b>Медиа стало:</b> <code>{media_type or 'нет'}</code>"
        )

    if changed_parts:
        notification = (
            f"✏️ <b>Сообщение изменено</b>\n"
            f"👤 <b>От:</b>     {sender_name}\n"
            f"{user_id_line(message.from_user.id if message.from_user else None)}"
            f"💬 <b>Чат ID:</b> <code>{message.chat.id}</code>\n"
            f"🕒 <b>Время:</b>  {fmt_time()}\n\n"
            + "\n\n".join(changed_parts)
        )
        try:
            await bot.send_message(owner_chat_id, notification)
            logger.info(f"✏️ Изменение сообщения {message.message_id} залогировано владельцу ({owner_chat_id})")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление об измененном сообщении: {e}")

    await db.save_message(
        connection_id=conn_id,
        msg_id=message.message_id,
        chat_id=message.chat.id,
        sender_id=message.from_user.id if message.from_user else None,
        sender_name=sender_name,
        sender_username=sender_username,
        text=message.text,
        media_type=media_type,
        file_id=file_id,
        file_unique_id=file_unique_id,
        caption=message.caption
    )


@dp.deleted_business_messages()
async def on_deleted_business_messages(event: types.BusinessMessagesDeleted):
    """
    Срабатывает, когда собеседник или пользователь удаляет сообщения в подключенном бизнес-чате.
    """
    conn_id = event.business_connection_id
    conn = await db.get_connection(conn_id)
    if not conn or not conn["is_enabled"]:
        logger.warning(
            f"Неизвестное или отключённое бизнес-подключение {conn_id} — событие удаления проигнорировано"
        )
        return

    owner_user_id = conn["user_id"]
    owner_chat_id = conn["user_chat_id"]

    saved_messages = await db.get_messages_by_ids(
        connection_id=conn_id,
        chat_id=event.chat.id,
        msg_ids=event.message_ids
    )

    for record in saved_messages:
        sender_name = record["sender_name"] or "Неизвестно"
        sender_id = record["sender_id"]
        text = record["text"] or ""
        media_type = record["media_type"]
        file_id = record["file_id"]
        caption_text = record["caption"] or ""
        msg_date = record["date"]

        title = media_title(media_type, "deleted") if media_type else "🗑 <b>Удалено текстовое сообщение</b>"
        notification = (
            f"{title}\n"
            f"👤 <b>От:</b>     {sender_name}\n"
            f"{user_id_line(sender_id)}"
            f"💬 <b>Чат ID:</b> <code>{event.chat.id}</code>\n"
            f"🕒 <b>Время:</b>  {fmt_time()}\n"
        )

        if text:
            notification += f"\n📝 <b>Текст сообщения:</b>\n{quote_text(text)}\n"
        if caption_text:
            notification += f"\n📝 <b>Подпись к файлу:</b>\n{quote_text(caption_text)}\n"

        try:
            if file_id and media_type:
                if media_type == "photo":
                    await bot.send_photo(owner_chat_id, photo=file_id, caption=notification)
                elif media_type == "video":
                    await bot.send_video(owner_chat_id, video=file_id, caption=notification)
                elif media_type == "animation":
                    await bot.send_animation(owner_chat_id, animation=file_id, caption=notification)
                elif media_type == "voice":
                    await bot.send_voice(owner_chat_id, voice=file_id, caption=notification)
                elif media_type == "video_note":
                    await bot.send_video_note(owner_chat_id, video_note=file_id)
                    await bot.send_message(owner_chat_id, notification)
                elif media_type == "audio":
                    await bot.send_audio(owner_chat_id, audio=file_id, caption=notification)
                elif media_type == "document":
                    await bot.send_document(owner_chat_id, document=file_id, caption=notification)
                elif media_type == "sticker":
                    await bot.send_sticker(owner_chat_id, sticker=file_id)
                    await bot.send_message(owner_chat_id, notification)
            else:
                await bot.send_message(owner_chat_id, notification)

            logger.info(f"🔔 Удаленное сообщение {record['msg_id']} переслано владельцу ({owner_chat_id})")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление об удаленном сообщении: {e}")


@dp.inline_query()
async def on_inline_query(query: types.InlineQuery):
    target_username, text = parse_whisper_query(query.query)
    if not target_username:
        await query.answer([whisper_help_result()], cache_time=0, is_personal=True)
        return
    token = secrets.token_urlsafe(12)
    WHISPERS[token] = {
        "target_username": target_username,
        "sender_id": query.from_user.id,
        "text": text,
        "expires_at": time.time() + 3600,
    }
    await db.save_whisper(token, query.from_user.id, target_username, text, time.time() + 3600)
    result = whisper_inline_result(token, target_username, text)
    await query.answer([result], cache_time=0, is_personal=True)


@dp.callback_query(F.data.startswith("whisper:"))
async def on_whisper_open(callback: types.CallbackQuery):
    token = callback.data.split(":", 1)[1]
    secret = await db.get_whisper(token)
    if not secret or secret["expires_at"] < time.time():
        await db.delete_whisper(token)
        WHISPERS.pop(token, None)
        await callback.answer("Сообщение больше недоступно.", show_alert=True)
        return
    secret_data = dict(secret)
    is_sender = whisper_access_allowed(
        secret_data, callback.from_user.id, callback.from_user.username
    )
    if not is_sender:
        await callback.answer("Это сообщение предназначено другому пользователю.", show_alert=True)
        return
    await callback.answer(secret_data["text"], show_alert=True, cache_time=0)


@dp.message(CommandStart())
async def on_start_command(message: types.Message):
    """
    Инструкция при запуске бота в личке.
    """
    first_name = html.escape(message.from_user.first_name) if message.from_user else "друг"
    if message.from_user:
        await db.save_user(
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            first_name=message.from_user.first_name,
            username=message.from_user.username,
        )
    if not message.from_user:
        await message.answer("Не удалось определить пользователя.")
        return
    await ensure_owner_user_id(message.from_user.id)
    await message.answer(
        f"👁 <b>{BOT_NAME}</b> — <i>Ничего не скроется.</i>\n\n"
        f"Привет, <b>{first_name}</b>!\n\n"
        "Я помогаю сохранять историю твоих чатов в Telegram. "
        "Больше никто не сможет незаметно удалить сообщение, спрятать контент или потерять важное.\n\n"
        "<b>Что я умею:</b>\n"
        "• <b>Одноразовые медиа:</b> фото и видео с таймером просмотра [View Once].\n"
        "• <b>Удалённые сообщения:</b> текст, фото, видео, голосовые, кружки, документы и стикеры.\n"
        "• <b>Изменения в чате:</b> показываю исходный текст до правки.\n"
        "• <b>Мут чатов:</b> .mute и .unmute для мгновенной очистки сообщений.\n"
        "• <b>Игры:</b> крестики-нолики и КНБ прямо в чате.\n"
        "• <b>Шепот:</b> inline-сообщения, видимые только адресату и отправителю.\n"
        "• <b>.spam:</b> .spam (кол-во) (текст) или (текст,текст).\n\n"
        "<blockquote>🔒 <b>Open-Source:</b> Проект полностью открытый. "
        "Весь код прозрачен, а твои данные остаются в безопасности.</blockquote>",
        reply_markup=start_keyboard()
    )


@dp.callback_query(F.data == "game:ttt")
async def on_game_ttt(callback: types.CallbackQuery):
    await callback.answer()
    game = new_game(callback.from_user.id, 0, callback.from_user.full_name, "Ожидание соперника")
    GAMES[callback.message.chat.id] = game
    await callback.message.edit_text(game_invite_text(game), reply_markup=invite_keyboard(callback.message.chat.id))


@dp.callback_query(F.data == "game:rps")
async def on_game_rps(callback: types.CallbackQuery):
    await callback.answer()
    game = new_rps_game(callback.from_user.id, 0, callback.from_user.full_name, "Ожидание соперника")
    GAMES[callback.message.chat.id] = game
    await callback.message.edit_text("✊ <b>Камень, ножницы, бумага</b>\n\nТебе предлагают сыграть. Примешь вызов?", reply_markup=invite_keyboard(callback.message.chat.id))


@dp.callback_query(F.data.startswith("ttt_accept:"))
async def on_ttt_accept(callback: types.CallbackQuery):
    chat_id = int(callback.data.split(":", 1)[1])
    game = GAMES.get(chat_id)
    if not game or game.get("status") != "active":
        await callback.answer("Игра уже завершена или отменена.", show_alert=True)
        return
    if callback.from_user.id == game["owner_id"]:
        await callback.answer("Вызов должен принять собеседник.", show_alert=True)
        return
    game["opponent_id"] = callback.from_user.id
    game["opponent_name"] = callback.from_user.full_name
    game["invited"] = False
    await callback.answer("Игра началась!")
    if game.get("kind") == "rps":
        await callback.message.edit_text(
            "✊ <b>Камень, ножницы, бумага</b>\n\nВыбери свой ход:",
            reply_markup=rps_keyboard(chat_id),
        )
    else:
        await callback.message.edit_text(render_game(game), reply_markup=game_markup(game, chat_id))


@dp.callback_query(F.data.startswith("ttt_decline:"))
async def on_ttt_decline(callback: types.CallbackQuery):
    chat_id = int(callback.data.split(":", 1)[1])
    game = GAMES.pop(chat_id, None)
    await callback.answer("Игра отклонена.")
    if game:
        await callback.message.edit_text("🎮 <b>Крестики-нолики</b>\n\nИгра отклонена.")


@dp.callback_query(F.data.startswith("rps:"))
async def on_rps_choice(callback: types.CallbackQuery):
    _, raw_chat_id, choice = callback.data.split(":")
    chat_id = int(raw_chat_id)
    game = GAMES.get(chat_id)
    if not game or game.get("kind") != "rps" or game.get("invited"):
        await callback.answer("Сначала нужно принять игру.", show_alert=True)
        return
    if callback.from_user.id not in (game["owner_id"], game["opponent_id"]):
        await callback.answer("Ты не участник этой игры.", show_alert=True)
        return
    if not apply_rps_choice(game, callback.from_user.id, choice):
        await callback.answer("Ты уже сделал выбор.", show_alert=True)
        return
    if game["status"] == "active":
        await callback.answer("Выбор принят. Ждём второго игрока.")
        return
    winner = rps_result(game["owner_choice"], game["opponent_choice"])
    if winner == "draw":
        result = "🤝 Ничья!"
    else:
        winner_name = game["owner_name"] if winner == "owner" else game["opponent_name"]
        result = f"🏆 Победитель: <b>{winner_name}</b>"
    text = (
        "✊ <b>Камень, ножницы, бумага</b>\n\n"
        f"{game['owner_name']}: {RPS_CHOICES[game['owner_choice']]}\n"
        f"{game['opponent_name']}: {RPS_CHOICES[game['opponent_choice']]}\n\n{result}"
    )
    await callback.answer("Раунд завершён")
    await callback.message.edit_text(text)
    GAMES.pop(chat_id, None)


@dp.callback_query(F.data.startswith("ttt:"))
async def on_ttt_move(callback: types.CallbackQuery):
    _, raw_chat_id, raw_index = callback.data.split(":")
    chat_id, index = int(raw_chat_id), int(raw_index)
    game = GAMES.get(chat_id)
    if not game or game.get("invited"):
        await callback.answer("Сначала нужно принять игру.", show_alert=True)
        return
    if callback.from_user.id not in (game["owner_id"], game["opponent_id"]):
        await callback.answer("Ты не участник этой игры.", show_alert=True)
        return
    if not apply_move(game, index, callback.from_user.id):
        await callback.answer("Сейчас ход другого игрока или клетка занята.", show_alert=True)
        return
    await callback.answer("Ход принят")
    await callback.message.edit_text(render_game(game), reply_markup=None if game["status"] != "active" else game_markup(game, chat_id))
    if game["status"] != "active":
        GAMES.pop(chat_id, None)


@dp.message(Command("broadcast"))
async def on_broadcast(message: types.Message):
    if not message.from_user:
        return
    if not await is_owner_user(message.from_user.id):
        await message.answer("⛔ Команда доступна только владельцу бота.")
        return

    payload = message.text or ""
    parts = payload.split(maxsplit=1)
    if len(parts) < 2 and not message.reply_to_message:
        await message.answer(
            "📣 <b>Рассылка</b>\n\n"
            "Использование:\n"
            "• <code>/broadcast текст</code>\n"
            "• либо ответом на нужное сообщение командой <code>/broadcast</code>"
        )
        return

    target_message = message.reply_to_message
    broadcast_text = parts[1] if len(parts) > 1 else (target_message.text or target_message.caption or "")
    if not broadcast_text:
        await message.answer("Не нашёл текст для рассылки.")
        return

    sent = 0
    failed = 0
    chat_ids = await db.get_broadcast_chat_ids()

    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, broadcast_text)
            sent += 1
        except Exception:
            await db.mark_user_blocked(chat_id)
            failed += 1

    await message.answer(
        f"📣 <b>Рассылка завершена</b>\n\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}"
    )


@dp.message(Command("stats"))
async def on_stats(message: types.Message):
    if not message.from_user:
        return
    if not await is_owner_user(message.from_user.id):
        await message.answer("⛔ Команда доступна только владельцу бота.")
        return

    stats = await db.get_stats()
    await message.answer(
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 <b>Пользователей:</b> {stats['users_total']}\n"
        f"✅ <b>Активных пользователей:</b> {stats['users_active']}\n"
        f"🔗 <b>Business-подключений:</b> {stats['business_total']}\n"
        f"🟢 <b>Активных business-подключений:</b> {stats['business_active']}\n"
        f"💬 <b>Сохранённых сообщений:</b> {stats['messages_total']}\n"
        f"📎 <b>Сообщений с медиа:</b> {stats['media_total']}\n"
        f"🖼 <b>Медиа-сообщений по типам:</b> {stats['media_messages']}"
    )


@dp.callback_query(F.data == "how_to_connect")
async def on_how_to_connect(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🔌 <b>Как подключить бота?</b>\n\n"
        "1. Откройте свой профиль Telegram.\n"
        "2. Нажмите <b>✏️ Изменить</b>.\n"
        "3. Перейдите в <b>Автоматизацию чатов</b>.\n"
        "4. Введите юзернейм этого бота.\n"
        "5. Разрешите доступ к сообщениям.\n\n"
        "Если что-то не выходит — пиши мне: @xicge"
    )


@dp.callback_query(F.data == "want_same_bot")
async def on_want_same_bot(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        f"🛡 <b>Хочу такого же бота</b>\n\n"
        f"Привет. В Telegram много похожих ботов, но почти все они закрыты. "
        f"Вы не видите, как и где обрабатываются личные переписки, а это риск.\n\n"
        f"{BOT_NAME} — более прозрачный путь.\n\n"
        f"🔗 <a href=\"{REPO_URL}\">Исходный код на GitHub</a>"
    )


async def periodic_cleanup():
    while True:
        try:
            await asyncio.sleep(86400)
            await db.cleanup_old_messages(CACHE_DAYS)
            await db.delete_expired_whispers(time.time())
        except Exception as e:
            logger.error(f"Ошибка периодической очистки: {e}")


async def main():
    if not BOT_TOKEN:
        print("\n" + "=" * 60)
        print(" [!] ОШИБКА: BOT_TOKEN не задан в файле .env!")
        print(" 1. Создайте файл .env на основе .env.example")
        print(" 2. Получите токен в @BotFather и укажите его в .env")
        print(" 3. Запустите: python bot.py")
        print("=" * 60 + "\n")
        return

    await db.init_db()

    # Обновляем описание бота со ссылкой на репозиторий (видно в профиле бота)
    try:
        await bot.set_my_description(
            f"{BOT_NAME} — сохраняет удалённые сообщения и медиа с таймером "
            f"в твоём Telegram Business.\n\nИсходный код: {REPO_URL}"
        )
        await bot.set_my_short_description(
            f"{BOT_NAME} — ничего не скроется. Исходники: {REPO_URL}"
        )
        logger.info("Описание бота обновлено (set_my_description)")
    except Exception as e:
        logger.warning(f"Не удалось обновить описание бота: {e}")

    print("=" * 50)
    print(f"🚀 {BOT_NAME} Telegram Business Bot запущен!")
    print("=" * 50)

    asyncio.create_task(periodic_cleanup())
    try:
        await dp.start_polling(bot)
    except TelegramNetworkError as exc:
        print("\n[!] Не удалось подключиться к Telegram API.")
        print("Проверь интернет, DNS, VPN/прокси и доступ к api.telegram.org:443")
        print(f"Детали: {exc}\n")


if __name__ == "__main__":
    asyncio.run(main())

