#FrogBot v1.3.6
import os
import sqlite3
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

conn = sqlite3.connect('user_points.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS user_points (user_id INTEGER PRIMARY KEY, points INTEGER)''')
user_points = {user_id: points if points is not None else 0 for user_id, points in c.execute('SELECT * FROM user_points')}

intents = discord.Intents.default()
intents.guilds = intents.guild_messages = intents.message_content = intents.members = True
client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
        
    elif message.content.lower() == "/frog":
        await message.channel.send("🐸")
        
    elif message.content.lower() in ("/uwu", "uwu"):
        await message.channel.send("OwO")

    elif message.content.lower() == '/frog help':
        await message.channel.send('```\n• "/myrank, /mypoints, /frog rank, /frog points" - Check your points and rank. (*add "help" after for points rules*)\n• "/Frog" - Ribbit.\n• "/Frog help" - Display this help message.\n\nFor commands below, the user must have the "FrogBotUser" rank.\n\n• "/add [amount] @user" - Add points to a user.\n• "/remove [amount] @user" - Remove points from a user.\n• "/points @user" - Check points for a user.\n```')
   
    elif message.content.lower().startswith(('/myrank', '/mypoints', '/frog rank', '/frog points')):
        if 'help' in message.content.lower():
            await message.channel.send('```Points work at follows:\n1000 points - Tadpole Trekker\n2500 points - Puddle Pioneer\n5000 points - Jumping Junior\n10,000 points - Croaking Cadet\n25,000 points - Ribbit Ranger\n50,000 points - Frog Star\n100,000 points - Lily Legend\n250,000 points - Froggy Monarch\n500,000 points - Never Nourished Fat Frog\n1,000,000 points - Fat Frog\n\nBug report = 250 points\nError log included + 250 points\nVideo included + 500 points\n\nFeature request = 100 points\nDetailed/thought out + 250 points\n\nSubmitting a PR = 1000 points\nPR gets merged 2500 points\n\nHelping someone with a question = 100 points\n```')
        else:
            user_id = message.author.id
            user_points.setdefault(user_id, 0)
            sorted_user_points = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
            user_rank = sorted_user_points.index((user_id, user_points[user_id])) + 1
            await message.channel.send(f'Your rank is #{user_rank} with {user_points[user_id]} points!')

    elif message.content.lower() == "primary mod":
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

@client.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        await process_role_changes(after.id, before.roles, after.roles)

async def process_role_changes(user_id, before_roles, after_roles):
    if before_roles != after_roles:
        added_roles = [role for role in after_roles if role not in before_roles]
        removed_roles = [role for role in before_roles if role not in after_roles]

        if added_roles:
            await on_roles_added(user_id, added_roles)

        if removed_roles:
            await on_roles_removed(user_id, removed_roles)

async def on_roles_added(user_id, added_roles):
    user = await client.fetch_user(user_id)
    role_names = ', '.join([role.name for role in added_roles])
    
    channel_id = os.getenv('CHANNEL_ID')

    channel = client.get_channel(int(channel_id))
    
    if channel:
        await channel.send(f"Congratulations! {user.mention} has been granted the following role(s): {role_names}")

async def on_roles_removed(user_id, removed_roles):
    user = await client.fetch_user(user_id)
    role_names = ', '.join([role.name for role in removed_roles])

    channel_id = os.getenv('CHANNEL_ID')

    channel = client.get_channel(int(channel_id))
    
    if channel:
        await channel.send(f"Sorry to see you go! {user.mention} no longer has the following role(s): {role_names}")

client.run(TOKEN)