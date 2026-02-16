# modules.utils.database

from disnake.ext import commands
from typing import Dict, Optional
from core import config
import aiosqlite
import disnake
import asyncio
import logging
import time
import httpx

DATABASE_FILE = config.read().get('DATABASE_FILE')
SYNC_SECRET = config.read().get('FROGBOT_SYNC_SECRET')
FROGPILOT_URL = "https://www.frogpilot.com"

_connection_pool = []
MAX_POOL_SIZE = 5

async def get_connection():
    if _connection_pool:
        return _connection_pool.pop()
    return await aiosqlite.connect(DATABASE_FILE)

async def release_connection(conn):
    if len(_connection_pool) < MAX_POOL_SIZE:
        _connection_pool.append(conn)
    else:
        await conn.close()

async def initialize_database():
    try:
        async with aiosqlite.connect(DATABASE_FILE) as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_points (
                    user_id INTEGER PRIMARY KEY,
                    points INTEGER NOT NULL DEFAULT 0
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS checkmark_logs (
                    message_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS thread_languages (
                    thread_id INTEGER NOT NULL,
                    language TEXT NOT NULL,
                    PRIMARY KEY (thread_id, language)
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS language_usage_stats (
                    user_id INTEGER NOT NULL,
                    language TEXT NOT NULL,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, language)
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER,
                    channel_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    scheduled_time TIMESTAMP NOT NULL,
                    timezone TEXT NOT NULL DEFAULT 'UTC',
                    is_whiteboard BOOLEAN NOT NULL DEFAULT 0,
                    whiteboard_data TEXT,
                    is_cancelled BOOLEAN NOT NULL DEFAULT 0
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS wiki_search_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    query_text TEXT NOT NULL,
                    event_timestamp INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    queue_length INTEGER,
                    details TEXT
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS wiki_search_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    query_text TEXT NOT NULL,
                    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'queued', -- queued, processing, completed, failed, error
                    message_id INTEGER, -- ID of the message confirming queue position
                    result_message_id INTEGER, -- ID of the message containing the results
                    details TEXT
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS known_themes (
                    theme_key TEXT PRIMARY KEY,
                    theme_name TEXT NOT NULL,
                    author_name TEXT NOT NULL
                )
            ''')
            await conn.commit()
    except Exception as e:
        logging.error(f"Error initializing database: {e}")

async def db_access_with_retry(sql_operation, args=(), max_attempts=5, delay=1):
    for attempt in range(max_attempts):
        conn = None
        try:
            conn = await get_connection()
            async with conn.cursor() as cursor:
                await cursor.execute(sql_operation, args)
                if sql_operation.strip().upper().startswith('SELECT'):
                    results = await cursor.fetchall()
                    await release_connection(conn)
                    return results
                await conn.commit()
            await release_connection(conn)
            return
        except aiosqlite.OperationalError as e:
            if conn:
                await conn.close()
            logging.error(f"Failed to execute sql operation: {e}")
            if attempt == max_attempts - 1:
                raise
            await asyncio.sleep(delay)

async def sync_points_to_frogpilot(user_id: int, points: int):
    """Sync point totals to FrogPilot.com."""
    if not SYNC_SECRET:
        return

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{FROGPILOT_URL}/api/pond/sync-points",
                json={"userId": str(user_id), "points": points},
                headers={"Authorization": f"Bearer {SYNC_SECRET}"},
                timeout=5.0
            )
            if res.status_code != 200:
                logging.error(f"Sync failed (HTTP {res.status_code}): {res.text}")
    except Exception as e:
        logging.error(f"Failed to sync points to FrogPilot: {e}")

async def initialize_points_database(user):
    rows = await db_access_with_retry('SELECT points FROM user_points WHERE user_id = ?', (user.id,))
    if not rows:
        await db_access_with_retry('INSERT INTO user_points (user_id, points) VALUES (?, ?)', (user.id, 0))
        await sync_points_to_frogpilot(user.id, 0)
        return 0
    return rows[0][0]

async def update_points(user_id, points):
    try:
        await db_access_with_retry('UPDATE user_points SET points = ? WHERE user_id = ?', (points, user_id))
        asyncio.create_task(sync_points_to_frogpilot(user_id, points))
        return True
    except Exception as e:
        logging.error(f"Failed to update points: {e}")
        return False

async def get_user_points(user_id):
    rows = await db_access_with_retry('SELECT points FROM user_points WHERE user_id = ?', (user_id,))
    if rows:
        return rows[0][0]
    return 0

async def get_all_users_points():
    rows = await db_access_with_retry('SELECT user_id, points FROM user_points')
    return {user_id: points for user_id, points in rows}

async def log_checkmark_message_id(message_id, channel_id, timestamp):
    try:
        await db_access_with_retry('INSERT INTO checkmark_logs (message_id, channel_id, timestamp) VALUES (?, ?, ?)', (message_id, channel_id, timestamp))
        return True
    except Exception as e:
        logging.error(f"Failed to log checkmark message ID: {e}")
        return False

async def add_thread_language(thread_id: int, language: str):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute(
            "INSERT OR IGNORE INTO thread_languages (thread_id, language) VALUES (?, ?)",
            (thread_id, language.lower())
        )
        await db.commit()

async def remove_thread_language(thread_id: int, language: str):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute(
            "DELETE FROM thread_languages WHERE thread_id = ? AND language = ?",
            (thread_id, language.lower())
        )
        await db.commit()

async def get_thread_languages(thread_id: int) -> list[str]:
    rows = await db_access_with_retry(
        'SELECT language FROM thread_languages WHERE thread_id = ?',
        (thread_id,)
    )
    return [row[0] for row in rows]

async def clear_thread_data(thread_id: int):
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        await conn.execute('DELETE FROM thread_languages WHERE thread_id = ?', (thread_id,))
        await conn.execute('DELETE FROM checkmark_logs WHERE channel_id = ?', (thread_id,))
        await conn.commit()

async def update_language_usage(user_id: int, language: str):
    await db_access_with_retry(
        'INSERT INTO language_usage_stats (user_id, language, message_count) VALUES (?, ?, 1) '
        'ON CONFLICT(user_id, language) DO UPDATE SET message_count = message_count + 1',
        (user_id, language)
    )

async def get_language_usage(user_id: int) -> Dict[str, int]:
    rows = await db_access_with_retry(
        'SELECT language, message_count FROM language_usage_stats WHERE user_id = ?',
        (user_id,)
    )
    return {row[0]: row[1] for row in rows} if rows else {}

async def clear_language_usage(user_id: int):
    await db_access_with_retry(
        'DELETE FROM language_usage_stats WHERE user_id = ?',
        (user_id,)
    )

async def schedule_message(channel_id: int, author_id: int, content: str, scheduled_time: str, timezone: str = 'UTC', is_whiteboard: bool = False, whiteboard_data: str = None) -> int:
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                '''INSERT INTO scheduled_messages
                   (channel_id, author_id, content, scheduled_time, timezone, is_whiteboard, whiteboard_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (channel_id, author_id, content, scheduled_time, timezone, is_whiteboard, whiteboard_data)
            )
            await conn.commit()
            return cursor.lastrowid

async def get_scheduled_message(id: int) -> dict:
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.cursor() as cursor:
            await cursor.execute(
                'SELECT * FROM scheduled_messages WHERE id = ? AND is_cancelled = 0',
                (id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_user_scheduled_messages(author_id: int = None) -> list:
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.cursor() as cursor:
            if author_id is None:
                await cursor.execute(
                    'SELECT * FROM scheduled_messages WHERE is_cancelled = 0 ORDER BY scheduled_time'
                )
            else:
                await cursor.execute(
                    'SELECT * FROM scheduled_messages WHERE author_id = ? AND is_cancelled = 0 ORDER BY scheduled_time',
                    (author_id,)
                )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows] if rows else []

async def cancel_scheduled_message(id: int) -> bool:
    try:
        await db_access_with_retry(
            'UPDATE scheduled_messages SET is_cancelled = 1 WHERE id = ?',
            (id,)
        )
        return True
    except Exception as e:
        logging.error(f"Failed to cancel scheduled message {id}: {e}")
        return False

async def update_scheduled_message(id: int, content: str = None, scheduled_time: str = None, timezone: str = None, whiteboard_data: str = None) -> bool:
    updates = []
    params = []
    if content is not None:
        updates.append('content = ?')
        params.append(content)
    if scheduled_time is not None:
        updates.append('scheduled_time = ?')
        params.append(scheduled_time)
    if timezone is not None:
        updates.append('timezone = ?')
        params.append(timezone)
    if whiteboard_data is not None:
        updates.append('whiteboard_data = ?')
        params.append(whiteboard_data)
    if not updates:
        return False
    params.append(id)
    try:
        await db_access_with_retry(
            f'UPDATE scheduled_messages SET {", ".join(updates)} WHERE id = ?',
            tuple(params)
        )
        return True
    except Exception as e:
        logging.error(f"Failed to update scheduled message {id}: {e}")
        return False

async def log_wiki_search_event(user_id: int, query_text: str, event_type: str, queue_length: int, details: Optional[str] = None):
    try:
        current_timestamp = int(time.time())
        await db_access_with_retry(
            '''INSERT INTO wiki_search_log
               (user_id, query_text, event_timestamp, event_type, queue_length, details)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (user_id, query_text, current_timestamp, event_type, queue_length, details)
        )
    except Exception as e:
        logging.error(f"Failed to log wiki search event (user: {user_id}, query: '{query_text}', event: {event_type}): {e}", exc_info=True)

async def add_to_wiki_queue(user_id: int, guild_id: int, channel_id: int, query_text: str, message_id: int) -> Optional[int]:
    conn = None
    try:
        current_timestamp = int(time.time())
        conn = await get_connection()
        async with conn.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO wiki_search_queue
                   (user_id, guild_id, channel_id, query_text, request_timestamp, message_id, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'queued')""",
                (user_id, guild_id, channel_id, query_text, current_timestamp, message_id)
            )
            await conn.commit()
            request_id = cursor.lastrowid
        return request_id
    except Exception as e:
        logging.error(f"Failed to add to wiki queue (user: {user_id}, query: '{query_text}'): {e}", exc_info=True)
        return None
    finally:
        if conn:
            await release_connection(conn)

async def get_oldest_queued_wiki_request() -> Optional[Dict]:
    conn = None
    try:
        conn = await get_connection()
        conn.row_factory = aiosqlite.Row
        async with conn.cursor() as cursor:
            await cursor.execute(
                "SELECT id FROM wiki_search_queue WHERE status = 'queued' ORDER BY request_timestamp ASC LIMIT 1"
            )
            row_id_data = await cursor.fetchone()
            if not row_id_data:
                return None
            request_id = row_id_data["id"]
            await cursor.execute(
                "UPDATE wiki_search_queue SET status = 'processing' WHERE id = ?",
                (request_id,)
            )
            await cursor.execute("SELECT * FROM wiki_search_queue WHERE id = ?", (request_id,))
            updated_row_data = await cursor.fetchone()
            await conn.commit()
            return dict(updated_row_data) if updated_row_data else None
    except Exception as e:
        logging.error(f"Error getting oldest queued wiki request: {e}", exc_info=True)
        if conn:
            await conn.rollback()
        return None
    finally:
        if conn:
            await release_connection(conn)

async def update_wiki_request_status(request_id: int, status: str, result_message_id: Optional[int] = None, details: Optional[str] = None) -> bool:
    try:
        updates = ["status = ?"]
        params = [status]
        if details is not None:
            updates.append("details = ?")
            params.append(details)
        if result_message_id is not None:
            updates.append("result_message_id = ?")
            params.append(result_message_id)
        params.append(request_id)
        sql = f"UPDATE wiki_search_queue SET {', '.join(updates)} WHERE id = ?"
        await db_access_with_retry(sql, tuple(params))
        return True
    except Exception as e:
        logging.error(f"Failed to update wiki request {request_id} to status {status}: {e}", exc_info=True)
        return False

async def get_wiki_queue_position(request_id: int) -> Optional[int]:
    rows = await db_access_with_retry(
        "SELECT COUNT(*) FROM wiki_search_queue WHERE status = 'queued' AND id <= ?",
        (request_id,)
    )
    return rows[0][0] if rows and rows[0] else None

async def get_wiki_queued_count() -> int:
    rows = await db_access_with_retry(
        "SELECT COUNT(*) FROM wiki_search_queue WHERE status = 'queued'"
    )
    return rows[0][0] if rows and rows[0] else 0

async def get_wiki_processing_count() -> int:
    rows = await db_access_with_retry(
        "SELECT COUNT(*) FROM wiki_search_queue WHERE status = 'processing'"
    )
    return rows[0][0] if rows and rows[0] else 0

async def is_theme_known(theme_key: str) -> bool:
    rows = await db_access_with_retry(
        'SELECT 1 FROM known_themes WHERE theme_key = ?',
        (theme_key,)
    )
    return bool(rows)

async def add_known_theme(theme_key: str, theme_name: str, author_name: str):
    await db_access_with_retry(
        'INSERT INTO known_themes (theme_key, theme_name, author_name) VALUES (?, ?, ?)',
        (theme_key, theme_name, author_name)
    )

async def get_known_themes() -> list:
    rows = await db_access_with_retry('SELECT theme_key FROM known_themes')
    return [row[0] for row in rows] if rows else []

async def get_wiki_request_by_id(request_id: int) -> Optional[Dict]:
    conn = await get_connection()
    try:
        conn.row_factory = aiosqlite.Row
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM wiki_search_queue WHERE id = ?", (request_id,))
            row = await cursor.fetchone()
        await release_connection(conn)
        return dict(row) if row else None
    except Exception as e:
        logging.error(f"Error fetching wiki request by ID {request_id}: {e}", exc_info=True)
        if conn:
            await release_connection(conn)
        return None

class ThreadCleanupManager:
    def __init__(self, bot):
        self.bot = bot
        self._cleanup_task = None
        self.cleanup_handlers: Dict[str, callable] = {}

    async def cleanup_threads(self) -> Dict[str, int]:
        stats = {'threads': 0, 'reactions': 0, 'checkmarks': 0}
        try:
            thread_langs = await db_access_with_retry('SELECT DISTINCT thread_id FROM thread_languages')
            for (thread_id,) in thread_langs:
                if not self.bot.get_channel(thread_id):
                    await clear_thread_data(thread_id)
                    stats['threads'] += 1
            current_time = int(time.time())
            check_rows = await db_access_with_retry(
                'SELECT message_id, channel_id, timestamp FROM checkmark_logs'
            )
            for message_id, channel_id, timestamp in check_rows:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    await db_access_with_retry(
                        'DELETE FROM checkmark_logs WHERE message_id = ?',
                        (message_id,)
                    )
                    stats['checkmarks'] += 1
                    continue
                elapsed_time = current_time - timestamp
                if elapsed_time > (7 * 24 * 60 * 60):
                    await db_access_with_retry(
                        'DELETE FROM checkmark_logs WHERE message_id = ?',
                        (message_id,)
                    )
                    if isinstance(channel, disnake.Thread):
                        try:
                            await channel.delete()
                        except disnake.NotFound:
                            pass
                    stats['checkmarks'] += 1
            return stats
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
            return stats

class DatabaseCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cleanup_manager = ThreadCleanupManager(bot)
        self._cleanup_task = None

    async def periodic_cleanup(self):
        while True:
            try:
                stats = await self.cleanup_manager.cleanup_threads()
                total_cleaned = sum(stats.values())
                if total_cleaned > 0:
                    logging.info(
                        f"Cleanup completed: {stats['threads']} threads, "
                        f"{stats['checkmarks']} checkmarks, "
                        f"{stats['reactions']} reactions"
                    )
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(3600)

    @commands.Cog.listener()
    async def on_ready(self):
        await initialize_database()
        self._cleanup_task = asyncio.create_task(self.periodic_cleanup())
        logging.debug("Database initialized and cleanup task started.")

    def cog_unload(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
        async def cleanup():
            for conn in _connection_pool:
                await conn.close()
            _connection_pool.clear()
        asyncio.create_task(cleanup())

def setup(bot):
    bot.add_cog(DatabaseCog(bot))
