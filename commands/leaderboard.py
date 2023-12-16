# commands/leaderboard.py

import discord
from discord.ext import commands
import sqlite3

LEADERBOARD_CHANNEL_ID = 1178764276157141093
LEADERBOARD_MESSAGE_ID = None
LEADERBOARD_MESSAGE_FILE = 'leaderboard_message_id.txt'

def is_admin():
    async def predicate(ctx):
        author = ctx.message.author
        is_admin = author.guild_permissions.administrator
        print(f"Checking admin status for {author} (ID: {author.id}): {is_admin}")
        return is_admin
    return commands.check(predicate)

def get_leaderboard():
    conn = sqlite3.connect('user_points.db')
    c = conn.cursor()
    c.execute('SELECT user_id, points FROM user_points ORDER BY points DESC LIMIT 10')
    leaderboard_data = c.fetchall()
    conn.close()
    return leaderboard_data
    
def save_leaderboard_message_id(message_id):
    with open(LEADERBOARD_MESSAGE_FILE, 'w') as file:
        file.write(str(message_id))

def load_leaderboard_message_id():
    try:
        with open(LEADERBOARD_MESSAGE_FILE, 'r') as file:
            return int(file.read().strip())
    except FileNotFoundError:
        return None

@commands.command(name="init_leaderboard")
@is_admin()
async def init_leaderboard(ctx):
    global LEADERBOARD_MESSAGE_ID
    channel = ctx.bot.get_channel(LEADERBOARD_CHANNEL_ID)

    if not channel:
        await ctx.send("Leaderboard channel not found.")
        return

    leaderboard_data = get_leaderboard()

    embed = await format_leaderboard(ctx.bot, leaderboard_data)
    message = await channel.send(embed=embed)
    LEADERBOARD_MESSAGE_ID = message.id
    save_leaderboard_message_id(LEADERBOARD_MESSAGE_ID)
    await ctx.send("Leaderboard initialized.")
    
async def format_leaderboard(bot, leaderboard_data):
    guild = bot.guilds[0]
    embed = discord.Embed(title="Top 10 Leaderboard", color=discord.Color.red())

    for index, (user_id, points) in enumerate(leaderboard_data, start=1):
        member = guild.get_member(user_id)
        if member:
            display_name = member.display_name
        else:
            display_name = f"User ID {user_id}"

        embed.add_field(name=f"#{index} {display_name}", value=f"{points} points", inline=False)

    return embed
    
async def update_leaderboard(bot):
    global LEADERBOARD_MESSAGE_ID

    if LEADERBOARD_MESSAGE_ID is None:
        LEADERBOARD_MESSAGE_ID = load_leaderboard_message_id()

    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        print("Leaderboard channel not found.")
        return

    try:
        message = await channel.fetch_message(LEADERBOARD_MESSAGE_ID)
    except:
        leaderboard_data = get_leaderboard()
        embed = await format_leaderboard(bot, leaderboard_data)
        message = await channel.send(embed=embed)
        LEADERBOARD_MESSAGE_ID = message.id
        return

    leaderboard_data = get_leaderboard()
    new_embed = await format_leaderboard(bot, leaderboard_data)
    await message.edit(embed=new_embed)

def setup(bot):
    bot.add_command(init_leaderboard)
    bot.update_leaderboard = update_leaderboard
