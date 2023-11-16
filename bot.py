import os
import sqlite3
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

conn = sqlite3.connect('user_points.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS user_points (user_id INTEGER PRIMARY KEY, points INTEGER)''')
user_points = {user_id: points for user_id, points in c.execute('SELECT * FROM user_points')}

intents = discord.Intents.default()
intents.guilds = intents.guild_messages = intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
        
    elif message.content.lower() == "/frog":
        await message.channel.send("🐸")

    elif message.content.lower().startswith('/frog help'):
        help_message = (
            '```\n- "/myrank, /mypoints, /frog rank" - Check your points and rank. All users may use this.\n- "/Frog" - Ribbit.\n- "/Frog help" - Display this help message.\n\nFor commands below, the user must have the "FrogBotUser" rank.\n\n- "/add [amount] @user" - Add points to a user.\n- "/remove [amount] @user" - Remove points from a user.\n- "/points @user" - Check points for a user.\n```')
        await message.channel.send(help_message)

    elif message.content.lower() in ('/myrank', '/mypoints', '/frog rank'):
        user_id = message.author.id
        user_points.setdefault(user_id, 0)
        sorted_user_points = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
        user_rank = sorted_user_points.index((user_id, user_points[user_id])) + 1
        await message.channel.send(f'Your rank is #{user_rank} with {user_points[user_id]} points!')


    elif "PRIMARY MOD" in message.content:
        await message.channel.send(':eyes:')

    frog_ai_user_role = discord.utils.get(message.guild.roles, name="FrogBotUser")

    def permission_check():
        return frog_ai_user_role in message.author.roles

    if (message.content.startswith(('/add ', '/remove ', '/points ')) and
            not permission_check()):
        await message.channel.send('You do not have permission to use this command. Check "/FrogBot help" for further info.')
        return

    if message.content.startswith(('/add ', '/remove ', '/points ')):
        command, mentioned_user = message.content.split()[0], message.mentions[0] if message.mentions else None
        if not mentioned_user:
            await message.channel.send(f'Please mention a user to {command.lower()} points for.')
        else:
            user_id = mentioned_user.id
            user_points.setdefault(user_id, 0)

            if command == '/add':
                points_to_modify = int(message.content.split()[1])
                c.execute('UPDATE user_points SET points = points + ? WHERE user_id = ?', (points_to_modify, user_id))
                user_points[user_id] += points_to_modify
                await message.channel.send(f'Added {points_to_modify} points to {mentioned_user.mention}\'s total!')
            elif command == '/remove':
                points_to_modify = int(message.content.split()[1])
                c.execute('UPDATE user_points SET points = points - ? WHERE user_id = ?', (points_to_modify, user_id))
                user_points[user_id] -= points_to_modify
                await message.channel.send(f'Removed {points_to_modify} points from {mentioned_user.mention}\'s total!')
            elif command == '/points':
                await message.channel.send(f'{mentioned_user.mention} has {user_points[user_id]} points!')

        conn.commit()

client.run(TOKEN)