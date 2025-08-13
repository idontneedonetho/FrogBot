# modules.theme_monitor

from modules.utils.database import is_theme_known, add_known_theme
from disnake.ext import commands
from datetime import datetime
import logging
import asyncio
import disnake
import gitlab
import re

class ThemeMonitorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gl = None
        self.project = None
        self.channel_id = 1276594550420275220
        self.role_id = 1374192170138992700
        self.init_gitlab()
        
    def init_gitlab(self):
        try:
            self.gl = gitlab.Gitlab('https://gitlab.com')
            self.project = self.gl.projects.get('FrogAi/FrogPilot-Resources-Submissions')
            logging.info("GitLab connected")
        except Exception as e:
            logging.error(f"GitLab init failed: {e}")
    
    def parse_theme(self, message: str):
        patterns = [
            r'Added Theme:\s*([^~\s]+)~([^\s]+)',
            r'Added Distance Icons:\s*([^~\s]+)~([^\s]+)',
            r'Added Steering Wheel:\s*([^~\s]+)~([^\s]+)'
        ]
        for pattern in patterns:
            if match := re.search(pattern, message):
                return match.group(1), match.group(2)
        return None
    
    async def notify(self, theme_name: str, author_name: str):
        try:
            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                return
            message = f'The "{theme_name}" theme was added by "{author_name}"!'
            embed = disnake.Embed(
                title="🎨 New Theme Submission!",
                description=message,
                color=disnake.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Theme", value=theme_name, inline=True)
            embed.add_field(name="Author", value=author_name, inline=True)
            embed.set_footer(text="FrogPilot Theme Monitor")
            role_mention = ""
            if role := channel.guild.get_role(self.role_id):
                role_mention = f"{role.mention} "
            await channel.send(content=f"{role_mention}{message}", embed=embed)
            logging.info(f"Posted: {theme_name} by {author_name}")
        except Exception as e:
            logging.error(f"Notification failed: {e}")
    
    async def load_existing_themes(self):
        if not self.project:
            return
        try:
            branches = ["Distance-Icons", "Steering-Wheels", "Themes"]
            for branch in branches:
                commits = self.project.commits.list(
                    ref_name=branch,
                    per_page=50,
                    iterator=True
                )
                for commit in commits:
                    if theme_info := self.parse_theme(commit.message):
                        theme_name, author_name = theme_info
                        theme_key = f"{theme_name}~{author_name}"
                        await add_known_theme(theme_key, theme_name, author_name)
                    await asyncio.sleep(0.1)
                logging.info(f"Loaded themes from {branch} branch")
            logging.info("Loaded existing themes into database")
        except Exception as e:
            logging.error(f"Load existing failed: {e}")
    
    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_existing_themes()
    
    @commands.Cog.listener()
    async def on_webhook_gitlab(self, payload):
        try:
            if payload.get('object_kind') == 'push':
                commits = payload.get('commits', [])
                for commit in commits:
                    if theme_info := self.parse_theme(commit.get('message', '')):
                        theme_name, author_name = theme_info
                        theme_key = f"{theme_name}~{author_name}"
                        if not await is_theme_known(theme_key):
                            await add_known_theme(theme_key, theme_name, author_name)
                            await self.notify(theme_name, author_name)
        except Exception as e:
            logging.error(f"Webhook processing failed: {e}")

def setup(bot):
    bot.add_cog(ThemeMonitorCog(bot))