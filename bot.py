#FrogBot v1.3.7
import asyncio
import discord
import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
channel_id = int(os.getenv('CHANNEL_ID'))

conn = sqlite3.connect('user_points.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS user_points (user_id INTEGER PRIMARY KEY, points INTEGER)''')
user_points = {user_id: points or 0 for user_id, points in c.execute('SELECT * FROM user_points')}

intents = discord.Intents.all()
client = discord.Client(intents=intents)

emoji_points = {
  "🐞": 250, 
  "📜": 250, 
  "📹": 500, 
  "💡": 100, 
  "🧠": 250, 
  "❤️": 100,
}

emoji_messages = {
  "🐞": " has been awarded {points} points for their bug report!",
  "📜": " has been awarded {points} points for including an error log in their bug report!",
  "📹": " has been awarded {points} points for including footage in their bug report!",
  "💡": " has been awarded {points} points for their feature request!",
  "🧠": " has been awarded {points} points for their well thought out feature request!",
  "❤️": " has been awarded {points} points for being a good frog!",
}

role_thresholds = {
  1000: '1178750004869996574', 2500: '1178751163462586368', 
  5000: '1178751322506416138', 10000: '1178751607509364828',
  25000: '1178751819434963044', 50000: '1178751897855856790',
  100000: '1178751985760079995', 250000: '1178752169894223983',
  500000: '1178752236717883534', 1000000: '1178752300592922634'
}

@client.event
async def on_ready():
  print(f'{client.user} has connected to Discord!')
  for guild in client.guilds:
    await update_roles_on_startup(guild)

async def update_roles_on_startup(guild):
  channel = client.get_channel(channel_id)

  if not channel:
    return

  for member in guild.members:
    if member.bot:
      continue

    user_id = member.id
    user_points_val = user_points.get(user_id, 0)
    new_roles = await update_roles(member, user_points_val)
    if new_roles:
      role_names = ', '.join([role.name for role in new_roles])
      await channel.send(f"Congratulations! {member.mention} has been granted the following role: {role_names}!")

@client.event
async def on_thread_create(thread):
  try:
    await asyncio.sleep(0.1)

    if thread.parent_id == 1162100167110053888:
      emojis_to_add = ["🐞", "📜", "📹"]

    if thread.parent_id in [1167651506560962581, 1160318669839147259]:
      emojis_to_add = ["💡", "🧠"]

    first_message = await thread.fetch_message(thread.id)
    for emoji in emojis_to_add:
      await first_message.add_reaction(emoji)

  except Exception as e:
    print(f"Error in on_thread_create: {e}")

@client.event
async def on_raw_reaction_add(payload):
  if payload.emoji.name not in emoji_points:
    return

  guild = client.get_guild(payload.guild_id)
  user = guild.get_member(payload.user_id)
  if user is None or "FrogBotUser" not in [role.name for role in user.roles]:
    return

  channel = client.get_channel(payload.channel_id)
  message = await channel.fetch_message(payload.message_id)
  user_id = message.author.id

  points_to_add = emoji_points[payload.emoji.name]
  user_points[user_id] = user_points.get(user_id, 0) + points_to_add
  c.execute('UPDATE user_points SET points = ? WHERE user_id = ?', (user_points[user_id], user_id))

  message_custom = emoji_messages.get(payload.emoji.name, "")
  if message_custom:
    message_custom_formatted = message_custom.format(points=points_to_add)
    await channel.send(f'{message.author.mention}{message_custom_formatted}')

  else:
    points_formatted = "{:,}".format(user_points[user_id])
    await channel.send(f'{message.author.mention} has been awarded {points_to_add} points! They now have {points_formatted} points.')

  await update_roles(message.author, user_points[user_id])
  conn.commit()

@client.event
async def on_message(message):
  if message.author == client.user:
    return

  elif ':coolfrog:' in message.content:
    await message.channel.send('<:coolfrog:1168605051779031060>')

  elif ':frog:' in message.content or message.content.lower() == "/frog":
    await message.channel.send(":frog:")

  elif any(keyword in message.content.lower() for keyword in ["/uwu", "uwu", "uWu", "WuW"]):
    await message.channel.send("OwO")

  elif any(keyword in message.content.lower() for keyword in ["/owo", "owo", "oWo", "OwO"]):
    await message.channel.send("UwU")

  elif message.content.lower() == '/frog help':
    help_message = '```\n• "/myrank, /mypoints, /frog rank, /frog points" - Check your points and rank. (*add "help" after for points rules*)\n• "/Frog" - Ribbit.\n• "/Frog help" - Display this help message.\n\nFor commands below, the user must have the "FrogBotUser" rank.\n\n• "/add [amount] @user" - Add points to a user.\n• "/remove [amount] @user" - Remove points from a user.\n• "/points @user" - Check points for a user.\n```'
    await message.channel.send(help_message)

  elif message.content.startswith(('/myrank', '/mypoints', '/frog rank', '/frog points')):
    if 'help' in message.content.lower():
      help_message = '```Points work as follows:\n\n1000 points - Tadpole Trekker\n2500 points - Puddle Pioneer\n5000 points - Jumping Junior\n10,000 points - Croaking Cadet\n25,000 points - Ribbit Ranger\n50,000 points - Frog Star\n100,000 points - Lily Legend\n250,000 points - Froggy Monarch\n500,000 points - Never Nourished Fat Frog\n1,000,000 points - Frog Daddy\n\nBug report = 250 points\nError log included += 250 points\nVideo included += 500 points\n\nFeature request = 100 points\nDetailed/thought out += 250 points\n\nSubmitting a PR = 1000 points\nPR gets merged += 2500 points\n\nHelping someone with a question = 100 points\n```'
      await message.channel.send(help_message)

    else:
      user_id = message.author.id
      user_points.setdefault(user_id, 0)
      sorted_user_points = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
      user_rank = sorted_user_points.index((user_id, user_points[user_id])) + 1
      points_formatted = "{:,}".format(user_points[user_id])
      await message.channel.send(f'Your rank is #{user_rank} with {points_formatted} points!')

  elif "PRIMARY MOD" in message.content:
    await message.channel.send(':eyes:')

  frog_ai_user_role = discord.utils.get(message.guild.roles, name="FrogBotUser")
  def permission_check():
    return frog_ai_user_role in message.author.roles

  if message.content.startswith(('/add ', '/remove ', '/points ')) and not permission_check():
    await message.channel.send('You do not have permission to use this command. Check "/FrogBot help" for further info.')
    return

  if message.content.startswith(('add ', 'remove ', '/points ')):
    command, mentioned_user = message.content.split()[0], message.mentions[0] if message.mentions else None
    if not mentioned_user:
      await message.channel.send(f'Please mention a user to {command.lower()} points for.')

    else:
      user_id = mentioned_user.id
      user_points.setdefault(user_id, 0)

      if command == 'add':
        points_to_modify = int(message.content.split()[1])
        c.execute('UPDATE user_points SET points = points + ? WHERE user_id = ?', (points_to_modify, user_id))
        user_points[user_id] += points_to_modify
        points_formatted = "{:,}".format(user_points[user_id])
        await message.channel.send(f'Added {points_to_modify} points to {mentioned_user.mention}\'s total! Now they have {points_formatted} points.')

      elif command == 'remove':
        points_to_modify = int(message.content.split()[1])
        c.execute('UPDATE user_points SET points = points - ? WHERE user_id = ?', (points_to_modify, user_id))
        user_points[user_id] -= points_to_modify

      elif command == '/points':
        points_formatted = "{:,}".format(user_points[user_id])
        await message.channel.send(f'{mentioned_user.mention} has {points_formatted} points!')

      await update_roles(mentioned_user, user_points[user_id])

  conn.commit()

@client.event
async def on_member_update(before, after):
  if before.roles != after.roles:
    await process_role_changes(after.id, before.roles, after.roles)

async def process_role_changes(user_id, before_roles, after_roles):
  added_roles = [role for role in after_roles if role not in before_roles]
  removed_roles = [role for role in before_roles if role not in after_roles]
  if added_roles:
    await on_roles_added(user_id, added_roles)
  if removed_roles:
    await on_roles_removed(user_id, removed_roles)

async def on_roles_added(user_id, added_roles):
  user = await client.fetch_user(user_id)
  role_names = ', '.join([role.name for role in added_roles])
  channel = client.get_channel(channel_id)

  if channel:
    await channel.send(f"Congratulations! {user.mention} has been granted the following role: {role_names}!")

async def on_roles_removed(user_id, removed_roles):
  user = await client.fetch_user(user_id)
  role_names = ', '.join([role.name for role in removed_roles])

async def update_roles(member, user_points):
  roles_to_remove = [member.guild.get_role(int(role_id)) for role_id in role_thresholds.values() if member.guild.get_role(int(role_id)) in member.roles]
  eligible_role = None
 
  for points, role_id in sorted(role_thresholds.items(), key=lambda x: x[0], reverse=True):
    if user_points >= points:
      eligible_role = member.guild.get_role(int(role_id))
      break

  new_roles = []

  if eligible_role and eligible_role not in member.roles:
    new_roles.append(eligible_role)
    await member.add_roles(eligible_role)

  for role in roles_to_remove:
    if role != eligible_role:
      await member.remove_roles(role)

  return new_roles

client.run(TOKEN)
