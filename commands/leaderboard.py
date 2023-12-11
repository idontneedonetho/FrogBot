# commands/leaderboard.py

from discord.ext import commands
import sqlite3
print('Leaderboard.py loaded')

def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

def get_leaderboard():
    conn = sqlite3.connect('user_points.db')
    c = conn.cursor()
    c.execute('SELECT user_id, points FROM user_points ORDER BY points DESC LIMIT 25')
    leaderboard_data = c.fetchall()
    conn.close()
    return leaderboard_data

@commands.command(name="top", aliases=["topusers"])
@commands.check(is_admin())
async def top25_command(ctx):
    leaderboard_data = get_leaderboard()

    if not leaderboard_data:
        await ctx.send("The leaderboard is empty.")
        return

    leaderboard_str = ">>> Top 25 Leaderboard:\n"
    for index, (user_id, points) in enumerate(leaderboard_data, start=1):
        try:
            user = await ctx.guild.fetch_member(user_id)
            leaderboard_str += f"{index}. {user.display_name}: {points} points\n"
        except:
            leaderboard_str += f"{index}. User ID {user_id}: {points} points\n"

    await ctx.send(leaderboard_str)

def setup(bot):
    bot.add_command(top25_command)
