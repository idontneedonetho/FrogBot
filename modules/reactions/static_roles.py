import sqlite3
import json
from discord.ext import commands

class RolePersistence(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'user_role_database.db'
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.initialize_database()

    def initialize_database(self):
        """Create the database table if it doesn't already exist."""
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS user_roles (
                                user_id TEXT PRIMARY KEY,
                                roles TEXT,
                                guild_id TEXT)''')
        self.conn.commit()

    async def on_member_remove(self, member):
        """Triggered when a member leaves the server."""
        roles = [role.id for role in member.roles if role.is_bot_managed() is False]
        # Convert the list of roles to a JSON string for storage
        roles_str = json.dumps(roles)
        self.cursor.execute('INSERT OR REPLACE INTO user_roles (user_id, roles, guild_id) VALUES (?, ?, ?)',
                            (str(member.id), roles_str, str(member.guild.id)))
        self.conn.commit()

    async def on_member_join(self, member):
        """Triggered when a member joins the server."""
        self.cursor.execute('SELECT roles FROM user_roles WHERE user_id = ? AND guild_id = ?',
                            (str(member.id), str(member.guild.id)))
        result = self.cursor.fetchone()
        if result:
            roles_ids = json.loads(result[0])
            roles = [member.guild.get_role(role_id) for role_id in roles_ids if member.guild.get_role(role_id)]
            await member.add_roles(*roles)

    @commands.Cog.listener()
    async def on_ready(self):
        """Periodic check to reassign roles can be initiated here if needed."""
        pass

def setup(bot):
    bot.add_cog(RolePersistence(bot))
