# modules.auto_backup

from datetime import datetime, timedelta, timezone
from modules.utils.database import DATABASE_FILE
from disnake.ext import commands
from disnake import Embed, Color
from core import Config, CONFIG
import asyncio
import logging
import aiohttp
import base64

class GitHubBackup:
    def __init__(self, token: str, owner: str):
        self.token = token
        self.owner = owner
        self.repo = 'FrogBot_DB_Backup'
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.db_file = DATABASE_FILE

    async def backup(self) -> tuple[bool, str]:
        try:
            with open(self.db_file, 'rb') as f:
                content = base64.b64encode(f.read()).decode()
            async with aiohttp.ClientSession() as session:
                filename = self.db_file.split('/')[-1]
                url = f'https://api.github.com/repos/{self.owner}/{self.repo}/contents/{filename}'
                async with session.get(url, headers=self.headers) as resp:
                    if resp.status == 200:
                        current_file = await resp.json()
                        sha = current_file.get('sha')
                    else:
                        sha = None
                data = {
                    'message': f'Backup {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}',
                    'content': content
                }
                if sha:
                    data['sha'] = sha
                async with session.put(url, headers=self.headers, json=data) as resp:
                    if resp.status == 200 or resp.status == 201:
                        commits_url = f'https://api.github.com/repos/{self.owner}/{self.repo}/commits'
                        async with session.get(commits_url, headers=self.headers) as commit_resp:
                            if commit_resp.status == 200:
                                commits = await commit_resp.json()
                                if commits:
                                    commit_sha = commits[0]['sha']
                                    logging.info("Backup successful")
                                    return True, commit_sha
                        logging.error("Failed to get commit SHA")
                        return True, None
                    else:
                        error_msg = await resp.text()
                        logging.error(f"Backup failed with status {resp.status}: {error_msg}")
                        return False, None
        except Exception as e:
            logging.error(f"Backup failed: {str(e)}")
            return False, None

class BackupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        config = Config(CONFIG['CONFIG_FILE']).read()
        self.backup_handler = GitHubBackup(
            token=config['GITHUB_TOKEN'],
            owner=config['GITHUB_USERNAME']
        )
        self.owner_id = 126123710435295232
        self.backup_task = self.bot.loop.create_task(self.scheduled_backup())
        logging.info("Scheduled daily backup task initialized")

    async def create_backup_embed(self, success: bool, scheduled: bool = False, sha: str = None) -> Embed:
        if success:
            embed = Embed(
                title="✅ Backup Successful",
                description="Database has been successfully backed up to GitHub.",
                color=Color.green()
            )
        else:
            embed = Embed(
                title="❌ Backup Failed",
                description="Failed to backup database to GitHub. Check logs for details.",
                color=Color.red()
            )
        embed.add_field(
            name="Timestamp", 
            value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>",
            inline=True
        )
        embed.add_field(
            name="Type",
            value="Scheduled" if scheduled else "Manual",
            inline=True
        )
        embed.add_field(
            name="Commit",
            value=f"[{sha[:7]}](https://github.com/{self.backup_handler.owner}/{self.backup_handler.repo}/commit/{sha})" if sha else "Unknown",
            inline=True
        )
        return embed

    async def scheduled_backup(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = datetime.now(timezone.utc)
            target = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            wait_time = (target - now).total_seconds()
            logging.info(f"Next scheduled backup in {wait_time/3600:.2f} hours")
            await asyncio.sleep(wait_time)
            try:
                success, sha = await self.backup_handler.backup()
                logging.info(f"Scheduled backup {'successful' if success else 'failed'}")
                if not success:
                    try:
                        owner = await self.bot.fetch_user(self.owner_id)
                        if owner:
                            embed = await self.create_backup_embed(success, scheduled=True, sha=sha)
                            await owner.send(embed=embed)
                    except Exception as e:
                        logging.error(f"Failed to send DM to owner: {e}")
            except Exception as e:
                logging.error(f"Error during scheduled backup: {str(e)}")

    def cog_unload(self):
        if hasattr(self, 'backup_task'):
            self.backup_task.cancel()

    @commands.slash_command(name="backup")
    @commands.is_owner()
    async def backup(self, inter):
        await inter.response.defer()
        success, sha = await self.backup_handler.backup()
        embed = await self.create_backup_embed(success, scheduled=False, sha=sha)
        await inter.followup.send(embed=embed)

def setup(bot):
    bot.add_cog(BackupCog(bot))