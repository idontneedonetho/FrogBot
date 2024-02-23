import sqlite3
import json
import time
        
DATABASE_FILE = 'user_role_database.db'

async def initialize_database(self):
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS user_roles (
                                user_id TEXT PRIMARY KEY,
                                roles TEXT,
                                guild_id TEXT)''')
        conn.commit()
        cursor.close()

async def on_member_remove(self, member):
    """Triggered when a member leaves the server."""
    roles = [role.id for role in member.roles if role.is_bot_managed() is False]
    # Convert the list of roles to a JSON string for storage
    roles_str = json.dumps(roles)
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO user_roles (user_id, roles, guild_id) VALUES (?, ?, ?)',
                        (str(member.id), roles_str, str(member.guild.id)))
        conn.commit()
        cursor.close()

async def on_member_join(self, member):
    """Triggered when a member joins the server."""
    roles = [role.id for role in member.roles if role.is_bot_managed() is False]
    # Convert the list of roles to a JSON string for storage
    roles_str = json.dumps(roles)
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT roles FROM user_roles WHERE user_id = ? AND guild_id = ?',
                        (str(member.id), str(member.guild.id)))
        result = cursor.fetchone()
        if result:
            roles_ids = json.loads(result[0])
            roles = [member.guild.get_role(role_id) for role_id in roles_ids if member.guild.get_role(role_id)]
            await member.add_roles(*roles)
        cursor.close()
