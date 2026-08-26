import asyncio
import logging
import html
from io import BytesIO
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

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
        [InlineKeyboardButton(text="📘 Как подключить бота", callback_data="how_to_connect")],
        [InlineKeyboardButton(text="🛡 Хочу такого же бота", callback_data="want_same_bot")],
    ])


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

    # Проверяем, ответил ли владелец на сообщение с медиа
    is_owner_message = (message.from_user and message.from_user.id == owner_user_id)
    if is_owner_message and message.reply_to_message:
        replied = message.reply_to_message
        media_type, file_id, _ = extract_media(replied)

        # Если в отвеченном сообщении есть медиафайл, пытаемся скачать его локально и отправить владельцу в ЛС
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
        f"👁 <b>{BOT_NAME}</b>\n"
        f"<i>Ничего не скроется.</i>\n\n"
        f"Привет, <b>{first_name}</b>!\n\n"
        f"Я сохраняю всё, что обычно пытаются скрыть или удалить:\n\n"
        f"🗑 <b>Удалённые сообщения</b> — текст, фото, видео, голосовые и кружки.\n"
        f"✏️ <b>Изменённые сообщения</b> — вижу, что было до правки и что стало после.\n"
        f"📸 <b>Одноразовые фото/видео</b> — перехватываю и сохраняю навсегда.\n"
        f"🧩 <b>Документы и стикеры</b> — тоже остаются в истории.\n\n"
        f"Твоя бизнес-переписка под контролем.\n\n"
        f"👇 Подключи бизнес-аккаунт кнопкой ниже:",
        reply_markup=start_keyboard()
    )


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
        "🛡 <b>Хочу такого же бота</b>\n\n"
        "Привет. В Telegram много похожих ботов, но почти все они закрыты. "
        "Вы не видите, как и где обрабатываются личные переписки, а это риск.\n\n"
        "<b>iSeeAllRobot</b> — более прозрачный путь. "
        "Скоро я выложу исходный код, и уведомление придёт сюда. Тогда можно будет собрать своего бота, "
        "добавить свои функции, улучшить логику и даже монетизировать проект.\n\n"
        "Помогу и с сервером, и с запуском, и с деплоем.\n\n"
        "По вопросам: @xicge"
    )


async def periodic_cleanup():
    while True:
        try:
            await asyncio.sleep(86400)
            await db.cleanup_old_messages(CACHE_DAYS)
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

