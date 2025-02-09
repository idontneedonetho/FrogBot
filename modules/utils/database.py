# modules.utils.database

from disnake.ext import commands
from core import config
from typing import Dict
import aiosqlite
import disnake
import asyncio
import logging
import time

DATABASE_FILE = config.read().get('DATABASE_FILE')

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
                CREATE TABLE IF NOT EXISTS translation_threads (
                    thread_id INTEGER PRIMARY KEY,
                    is_active BOOLEAN NOT NULL DEFAULT 1
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_language_preferences (
                    thread_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    language TEXT NOT NULL,
                    PRIMARY KEY (thread_id, user_id)
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

async def initialize_points_database(user):
    rows = await db_access_with_retry('SELECT points FROM user_points WHERE user_id = ?', (user.id,))
    if not rows:
        await db_access_with_retry('INSERT INTO user_points (user_id, points) VALUES (?, ?)', (user.id, 0))
        return 0
    return rows[0][0]

async def update_points(user_id, points):
    try:
        await db_access_with_retry('UPDATE user_points SET points = ? WHERE user_id = ?', (points, user_id))
        return True
    except Exception as e:
        logging.error(f"Failed to update points: {e}")
        return False

async def get_user_points(user_id):
    rows = await db_access_with_retry('SELECT points FROM user_points WHERE user_id = ?', (user_id,))
    if rows:
        return rows[0][0]
    return 0

async def log_checkmark_message_id(message_id, channel_id, timestamp):
    try:
        await db_access_with_retry('INSERT INTO checkmark_logs (message_id, channel_id, timestamp) VALUES (?, ?, ?)', (message_id, channel_id, timestamp))
        return True
    except Exception as e:
        logging.error(f"Failed to log checkmark message ID: {e}")
        return False

async def set_thread_active(thread_id: int, active: bool = True):
    await db_access_with_retry(
        'INSERT INTO translation_threads (thread_id, is_active) VALUES (?, ?) '
        'ON CONFLICT(thread_id) DO UPDATE SET is_active = ?',
        (thread_id, active, active)
    )

async def is_thread_active(thread_id: int) -> bool:
    rows = await db_access_with_retry(
        'SELECT is_active FROM translation_threads WHERE thread_id = ?',
        (thread_id,)
    )
    return bool(rows and rows[0][0])

async def set_user_language(thread_id: int, user_id: int, language: str):
    await db_access_with_retry(
        'INSERT INTO user_language_preferences (thread_id, user_id, language) VALUES (?, ?, ?) '
        'ON CONFLICT(thread_id, user_id) DO UPDATE SET language = ?',
        (thread_id, user_id, language, language)
    )

async def get_user_language(thread_id: int, user_id: int) -> str:
    rows = await db_access_with_retry(
        'SELECT language FROM user_language_preferences WHERE thread_id = ? AND user_id = ?',
        (thread_id, user_id)
    )
    return rows[0][0] if rows else None

async def add_thread_language(thread_id: int, language: str):
    await db_access_with_retry(
        'INSERT OR IGNORE INTO thread_languages (thread_id, language) VALUES (?, ?)',
        (thread_id, language)
    )

async def remove_thread_language(thread_id: int, language: str):
    await db_access_with_retry(
        'DELETE FROM thread_languages WHERE thread_id = ? AND language = ?',
        (thread_id, language)
    )

async def get_thread_languages(thread_id: int) -> list[str]:
    rows = await db_access_with_retry(
        'SELECT language FROM thread_languages WHERE thread_id = ?',
        (thread_id,)
    )
    return [row[0] for row in rows]

async def clear_thread_data(thread_id: int):
    """Centralized function to clear all data related to a thread"""
    async with aiosqlite.connect(DATABASE_FILE) as conn:
        await conn.execute('DELETE FROM translation_threads WHERE thread_id = ?', (thread_id,))
        await conn.execute('DELETE FROM user_language_preferences WHERE thread_id = ?', (thread_id,))
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

class ThreadCleanupManager:
    def __init__(self, bot):
        self.bot = bot
        self._cleanup_task = None
        self.cleanup_handlers: Dict[str, callable] = {}

    async def cleanup_threads(self) -> Dict[str, int]:
        stats = {'threads': 0, 'reactions': 0, 'checkmarks': 0}
        try:
            trans_rows = await db_access_with_retry('SELECT thread_id FROM translation_threads')
            for (thread_id,) in trans_rows:
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