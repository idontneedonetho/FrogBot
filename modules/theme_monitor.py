# modules.theme_monitor

from modules.utils.database import is_theme_known, add_known_theme
from disnake.ext import commands, tasks
from datetime import datetime
from github import Github
import logging
import disnake

class ThemeMonitorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = 1276594550420275220
        self.role_id = 1374192170138992700
        self.repo = "FrogAi/FrogPilot-Resources"
        self.branches = ["Distance-Icons", "Steering-Wheels", "Themes"]
        self.github = None
        self.repo_obj = None
        
    def init_github(self):
        try:
            token = getattr(self.bot, 'config', {}).get('GITHUB_TOKEN')
            self.github = Github(token) if token else Github()
            self.repo_obj = self.github.get_repo(self.repo)
            logging.info("GitHub connected")
        except Exception as e:
            logging.error(f"GitHub init failed: {e}")
    
    def parse_theme_from_path(self, path: str):
        base_name = path.split('/')[-1]
        name_no_ext = base_name.rsplit('.', 1)[0]
        if '~' in name_no_ext:
            theme_name, author = name_no_ext.split('~', 1)
            return theme_name, author
        return None
    
    async def notify(self, theme_name: str, author_name: str, commit_url: str = None):
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return
        display_theme = theme_name.replace('-', ' ').title()
        embed = disnake.Embed(
            title="🎨 New Theme Submission!",
            description=f'The "{display_theme}" theme was added by "{author_name}"!',
            color=disnake.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Theme", value=display_theme, inline=True)
        embed.add_field(name="Author", value=author_name, inline=True)
        if commit_url:
            embed.add_field(name="View Theme", value=f"[Click Here]({commit_url})", inline=False)
        embed.set_footer(text="FrogPilot Theme Monitor")
        role = channel.guild.get_role(self.role_id)
        role_mention = f"{role.mention} " if role else ""
        await channel.send(content=f"{role_mention}The \"{display_theme}\" theme was added by \"{author_name}\"!", embed=embed)
        logging.info(f"Posted: {display_theme} by {author_name}")
    
    async def load_existing_themes(self):
        for branch in self.branches:
            branch_obj = self.repo_obj.get_branch(branch)
            tree = self.repo_obj.get_git_tree(branch_obj.commit.sha, recursive=True)
            for item in tree.tree:
                if ('/' not in item.path) and (item.type in {"tree", "blob"}) and (theme_info := self.parse_theme_from_path(item.path)):
                    await add_known_theme(f"{theme_info[0]}~{theme_info[1]}", theme_info[0], theme_info[1])
        logging.info("Loaded existing themes into database")
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.init_github()
        await self.load_existing_themes()
        self.check_new_themes.start()
    
    @tasks.loop(minutes=5)
    async def check_new_themes(self):
        for branch in self.branches:
            branch_obj = self.repo_obj.get_branch(branch)
            tree = self.repo_obj.get_git_tree(branch_obj.commit.sha, recursive=True)
            for item in tree.tree:
                if ('/' not in item.path) and (item.type in {"tree", "blob"}) and (theme_info := self.parse_theme_from_path(item.path)):
                    theme_key = f"{theme_info[0]}~{theme_info[1]}"
                    if not await is_theme_known(theme_key):
                        commits = self.repo_obj.get_commits(sha=branch, path=item.path)
                        latest_url = None
                        for c in commits[:1]:
                            latest_url = c.html_url
                            break
                        await add_known_theme(theme_key, theme_info[0], theme_info[1])
                        await self.notify(theme_info[0], theme_info[1], latest_url)
    
    def cog_unload(self):
        self.check_new_themes.cancel()

def setup(bot):
    bot.add_cog(ThemeMonitorCog(bot))