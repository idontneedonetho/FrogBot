# modules.auto_backup

from datetime import datetime, time, timedelta, timezone
from modules.utils.database import DATABASE_FILE
from core import Config, CONFIG_FILE
from disnake.ext import commands
from disnake import Embed, Color
from typing import Optional
import asyncio
import logging
import base64
import aiohttp
import random
import os

REPO_NAME = 'FrogBot_DB_Backup'
DB_FILENAME = os.path.basename(DATABASE_FILE)

class GitHubBackup:
    def __init__(self, token: str, owner: str):
        self._token = token
        self._owner = owner
        self._headers = {
            'Authorization': f'Bearer {self._token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self._base_url = 'https://api.github.com'
        logging.info(f"Initializing backup for database: {DB_FILENAME}")
        logging.info(f"Database full path: {os.path.abspath(DATABASE_FILE)}")
        logging.info(f"GitHub owner: {owner}")
        logging.info(f"Repository name: {REPO_NAME}")

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> dict:
        async with aiohttp.ClientSession() as session:
            url = f"{self._base_url}/{endpoint}"
            logging.info(f"Making {method} request to: {url}")
            if 'json' in kwargs:
                logging.info(f"Request payload keys: {kwargs['json'].keys()}")
                if 'content' in kwargs['json']:
                    logging.info(f"Content length: {len(kwargs['json']['content'])}")
            async with session.request(method, url, headers=self._headers, **kwargs) as response:
                logging.info(f"Response status: {response.status}")
                if response.status >= 400:
                    body = await response.text()
                    logging.error(f"Error response body: {body}")
                response.raise_for_status()
                return await response.json() if response.content_length else None

    async def backup_database(self) -> bool:
        try:
            if not os.path.exists(DATABASE_FILE):
                logging.error(f"Database file not found: {DATABASE_FILE}")
                return False

            # Log file stats
            file_stats = os.stat(DATABASE_FILE)
            logging.info(f"Database file size: {file_stats.st_size} bytes")
            logging.info(f"Database file permissions: {oct(file_stats.st_mode)}")
            
            with open(DATABASE_FILE, 'rb') as f:
                content = f.read()
                logging.info(f"Read {len(content)} bytes from database file")
                encoded_content = base64.b64encode(content).decode()
                logging.info(f"Encoded content length: {len(encoded_content)}")
            try:
                current_file = await self._make_request(
                    'GET',
                    f'repos/{self._owner}/{REPO_NAME}/contents/{DB_FILENAME}'
                )
                sha = current_file['sha'] if current_file else None
            except:
                sha = None
            data = {
                'message': f'Backup {DB_FILENAME} - {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}',
                'content': encoded_content,
            }
            if sha:
                data['sha'] = sha
            await self._make_request(
                'PUT',
                f'repos/{self._owner}/{REPO_NAME}/contents/{DB_FILENAME}',
                json=data
            )
            logging.info(f"Successfully created backup of {DB_FILENAME}")
            return True
        except Exception as e:
            logging.error(f"Backup failed for {DB_FILENAME}: {e}")
            return False

class BackupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.backup_task: Optional[asyncio.Task] = None
        self._last_backup_time = None
        config = Config(CONFIG_FILE).read()
        try:
            self.backup_handler = GitHubBackup(
                token=config['GITHUB_TOKEN'],
                owner=config['GITHUB_USERNAME']
            )
        except KeyError as e:
            logging.error(f"Missing GitHub credentials in config: {e}")
            self.backup_handler = None

    def cog_unload(self):
        if self.backup_task:
            self.backup_task.cancel()

    async def schedule_backup(self):
        while True:
            try:
                now = datetime.now()
                target_time = time(hour=0, minute=0)
                next_run = datetime.combine(now.date(), target_time)
                if now.time() >= target_time:
                    next_run += timedelta(days=1)
                sleep_seconds = (next_run - now).total_seconds() + random.randint(-300, 300)
                await asyncio.sleep(sleep_seconds)
                if self._last_backup_time and self._last_backup_time.date() == now.date():
                    continue
                async with asyncio.timeout(600):
                    success = await self.backup_handler.backup_database()
                    if success:
                        self._last_backup_time = now
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Backup schedule error: {e}")
                await asyncio.sleep(300)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.backup_task and self.backup_handler:
            self.backup_task = self.bot.loop.create_task(self.schedule_backup())
            logging.info("Database backup scheduler started")

    @commands.slash_command(name="backup")
    @commands.is_owner()
    async def backup(self, inter):
        if not self.backup_handler:
            await inter.response.send_message(
                embed=Embed(
                    title="❌ Backup System Not Available",
                    description="The backup system is not properly configured.",
                    color=Color.red()
                )
            )
            return
        await inter.response.defer()
        try:
            success = await self.backup_handler.backup_database()
            embed = Embed(
                title="💾 Backup Status",
                description=f"```{'✅ Completed' if success else '❌ Failed'}```",
                color=Color.green() if success else Color.red()
            )
            embed.set_footer(text=f"Operation Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            await inter.followup.send(embed=embed)
        except Exception as e:
            error_embed = Embed(
                title="❌ Backup Operation Failed",
                description=f"```{str(e)}```",
                color=Color.red()
            )
            await inter.followup.send(embed=error_embed)

def setup(bot):
    bot.add_cog(BackupCog(bot))
