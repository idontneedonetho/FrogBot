# bot.py

frog_version = "v2 beta"
import discord
import asyncio
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os

from commands import uwu, owo

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise ValueError("Bot token not found in .env file. Please add it.")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents, case_insensitive=True)

try: # Help
    from commands import help
    help.setup(bot)
except ImportError as e:
    print(f"Error importing help: {e}")
except Exception as e:
    print(f"Error setting up help: {e}")

try: # Points
    from commands import points
    points.setup(bot)
except ImportError as e:
    print(f"Error importing points: {e}")
except Exception as e:
    print(f"Error setting up points: {e}")

try: # Leaderboard
    from commands import leaderboard
    leaderboard.setup(bot)
except ImportError as e:
    print(f"Error importing leaderboard: {e}")
except Exception as e:
    print(f"Error setting up leaderboard: {e}")

try: # Emoji
    from commands import emoji
except ImportError as e:
    print(f"Error importing emoji: {e}")
except Exception as e:
    print(f"Error setting up emoji: {e}")

try: # Roles
    from commands import roles
except ImportError as e:
    print(f"Error importing roles: {e}")
except Exception as e:
    print(f"Error setting up roles: {e}")
    
try: # Update
    from commands import update
    update.setup(bot)
except ImportError as e:
    print(f"Error importing update: {e}")
except Exception as e:
    print(f"Error settings up update: {e}")
    
try: # Restart
    from commands import restart
    restart.setup(bot)
except ImportError as e:
    print(f"Error importing restart: {e}")
except Exception as e:
    print(f"Error settings up restart: {e}")

last_used_responses = {"uwu": None, "owo": None}

@bot.event
async def on_ready():
    print(f"Ready {bot.user.name}")
    await roles.check_user_points(bot)
    await bot.change_presence(activity=discord.Game(name=f"version {frog_version}"))

@bot.event
async def on_raw_reaction_add(payload):
    user_id = payload.user_id
    guild_id = payload.guild_id
    guild = bot.get_guild(guild_id)
    member = guild.get_member(user_id)
    
    if member and member.guild_permissions.administrator:
        user = bot.get_user(user_id)
        user_points = points.initialize_points_database(bot, user)

        channel = bot.get_channel(payload.channel_id)
        await emoji.process_reaction(bot, payload, user_points)
        await roles.check_user_points(bot)
    else:
        print(f"{user.name} does not have the Administrator permission. Ignoring the reaction.")

@bot.event
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

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    content = message.content.lower()
    # Reactions
    if bot.user.mentioned_in(message) and len(message.content) == len(bot.user.mention):
        await message.channel.send(":frog:")
    if message.content == "uwu":
        await uwu.uwu(message)
    elif message.content == "owo":
        await owo.owo(message)
    elif message.content.lower() == "weeb":
        await message.channel.send('https://media1.tenor.com/m/rM6sdvGLYCMAAAAC/bonk.gif')
    elif ':coolfrog:' in message.content:
        await message.channel.send('<:coolfrog:1168605051779031060>')
    elif any(keyword in message.content.lower() for keyword in ['primary mod']):
        await message.channel.send(':eyes:')
    
    await bot.process_commands(message)

try:
    bot.run(TOKEN)
except Exception as e:
    print(f"An error occurred: {e}")
