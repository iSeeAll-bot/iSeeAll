import aiosqlite
from datetime import datetime, timedelta
from config import DB_PATH

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                first_name TEXT,
                username TEXT,
                is_blocked BOOLEAN DEFAULT 0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS business_connections (
                connection_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                user_chat_id INTEGER NOT NULL,
                can_reply BOOLEAN DEFAULT 0,
                is_enabled BOOLEAN DEFAULT 1,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                connection_id TEXT NOT NULL,
                msg_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                sender_id INTEGER,
                sender_name TEXT,
                sender_username TEXT,
                text TEXT,
                media_type TEXT,
                file_id TEXT,
                file_unique_id TEXT,
                caption TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(connection_id, chat_id, msg_id)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_business_msg 
            ON messages(connection_id, chat_id, msg_id)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS whispers (
                token TEXT PRIMARY KEY,
                sender_id INTEGER NOT NULL,
                target_username TEXT NOT NULL,
                text TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        await db.commit()


async def get_setting(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        """, (key, value))
        await db.commit()


async def set_muted_chat(connection_id: str, chat_id: int, muted: bool):
    await set_setting(f"mute:{connection_id}:{chat_id}", "1" if muted else "0")


async def is_chat_muted(connection_id: str, chat_id: int) -> bool:
    return (await get_setting(f"mute:{connection_id}:{chat_id}")) == "1"


async def save_whisper(token: str, sender_id: int, target_username: str, text: str, expires_at: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO whispers (token, sender_id, target_username, text, expires_at) VALUES (?, ?, ?, ?, ?)",
            (token, sender_id, target_username, text, expires_at),
        )
        await db.commit()


async def get_whisper(token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM whispers WHERE token = ?", (token,)) as cursor:
            return await cursor.fetchone()


async def delete_whisper(token: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM whispers WHERE token = ?", (token,))
        await db.commit()


async def delete_expired_whispers(now: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM whispers WHERE expires_at < ?", (now,))
        await db.commit()


async def save_user(user_id: int, chat_id: int, first_name: str | None, username: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, chat_id, first_name, username, is_blocked, last_seen, created_at)
            VALUES (?, ?, ?, ?, 0, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                chat_id = excluded.chat_id,
                first_name = excluded.first_name,
                username = excluded.username,
                is_blocked = 0,
                last_seen = excluded.last_seen
        """, (
            user_id,
            chat_id,
            first_name,
            username,
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        await db.commit()


async def mark_user_blocked(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_blocked = 1 WHERE chat_id = ?", (chat_id,))
        await db.commit()


async def get_broadcast_chat_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT chat_id FROM users WHERE is_blocked = 0
            UNION
            SELECT user_chat_id AS chat_id FROM business_connections WHERE is_enabled = 1
        """) as cursor:
            rows = await cursor.fetchall()
            return [row["chat_id"] for row in rows if row["chat_id"]]


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute("SELECT COUNT(*) AS total FROM users") as cursor:
            users_total = (await cursor.fetchone())["total"]

        async with db.execute("SELECT COUNT(*) AS total FROM users WHERE is_blocked = 0") as cursor:
            users_active = (await cursor.fetchone())["total"]

        async with db.execute("SELECT COUNT(*) AS total FROM business_connections") as cursor:
            business_total = (await cursor.fetchone())["total"]

        async with db.execute("SELECT COUNT(*) AS total FROM business_connections WHERE is_enabled = 1") as cursor:
            business_active = (await cursor.fetchone())["total"]

        async with db.execute("SELECT COUNT(*) AS total FROM messages") as cursor:
            messages_total = (await cursor.fetchone())["total"]

        async with db.execute("SELECT COUNT(*) AS total FROM messages WHERE media_type IS NOT NULL") as cursor:
            media_total = (await cursor.fetchone())["total"]

        async with db.execute("SELECT COUNT(*) AS total FROM messages WHERE media_type IN ('photo', 'video', 'animation', 'voice', 'video_note', 'audio', 'document', 'sticker')") as cursor:
            media_messages = (await cursor.fetchone())["total"]

        return {
            "users_total": users_total,
            "users_active": users_active,
            "business_total": business_total,
            "business_active": business_active,
            "messages_total": messages_total,
            "media_total": media_total,
            "media_messages": media_messages,
        }

async def save_connection(connection_id: str, user_id: int, user_chat_id: int, can_reply: bool, is_enabled: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO business_connections 
            (connection_id, user_id, user_chat_id, can_reply, is_enabled, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            connection_id,
            user_id,
            user_chat_id,
            1 if can_reply else 0,
            1 if is_enabled else 0,
            datetime.now().isoformat()
        ))
        await db.commit()

async def get_connection(connection_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM business_connections WHERE connection_id = ?
        """, (connection_id,)) as cursor:
            return await cursor.fetchone()

async def get_connections_by_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM business_connections WHERE user_id = ? AND is_enabled = 1
        """, (user_id,)) as cursor:
            return await cursor.fetchall()

async def save_message(
    connection_id: str,
    msg_id: int,
    chat_id: int,
    sender_id: int | None,
    sender_name: str,
    sender_username: str | None,
    text: str | None,
    media_type: str | None,
    file_id: str | None,
    file_unique_id: str | None,
    caption: str | None
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO messages 
            (connection_id, msg_id, chat_id, sender_id, sender_name, sender_username, text, media_type, file_id, file_unique_id, caption, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            connection_id,
            msg_id,
            chat_id,
            sender_id,
            sender_name,
            sender_username,
            text,
            media_type,
            file_id,
            file_unique_id,
            caption,
            datetime.now().isoformat()
        ))
        await db.commit()

async def get_messages_by_ids(connection_id: str, chat_id: int, msg_ids: list[int]):
    if not msg_ids:
        return []
    placeholders = ",".join("?" for _ in msg_ids)
    query = f"SELECT * FROM messages WHERE connection_id = ? AND chat_id = ? AND msg_id IN ({placeholders})"
    params = [connection_id, chat_id] + msg_ids
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            return await cursor.fetchall()

async def get_message(connection_id: str, chat_id: int, msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM messages
            WHERE connection_id = ? AND chat_id = ? AND msg_id = ?
        """, (connection_id, chat_id, msg_id)) as cursor:
            return await cursor.fetchone()

async def cleanup_old_messages(days: int):
    if days <= 0:
        return
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE date < ?", (cutoff,))
        await db.commit()
