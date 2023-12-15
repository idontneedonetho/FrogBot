# bot.py

frog_version = "v2 beta"
import discord
import asyncio
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timedelta
from discord.errors import HTTPException, NotFound
import os

user_request_times = {}
RATE_LIMIT = timedelta(seconds=15)

from commands import uwu, owo

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise ValueError("Bot token not found in .env file. Please add it.")

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True
intents.guild_messages = True
intents.reactions = True
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents, case_insensitive=True)

RESTART_FLAG_FILE = 'restart.flag'

try: # GPT
    from commands import GPT
except ImportError as e:
    print(f"Error importing GPT: {e}")
except Exception as e:
    print(f"Error setting up GPT: {e}")

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
    
    if os.path.exists(RESTART_FLAG_FILE):
        channel = bot.get_channel(1178764276157141093)
        
        if channel is not None:
            await channel.send("Bot is back online after restart.")
            os.remove(RESTART_FLAG_FILE)
        else:
            print("Channel not found. Make sure the channel ID is correct.")

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
        user = await bot.fetch_user(user_id)
        user_name = user.name
        print(f"{user_name} does not have the Administrator permission. Ignoring the reaction.")

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

def count_tokens(text):
    return len(text) // 4

async def fetch_reply_chain(message, max_tokens=4096):
    context = []
    tokens_used = 0

    while message.reference is not None and tokens_used < max_tokens:
        try:
            message = await message.channel.fetch_message(message.reference.message_id)
            message_content = message.content
            message_tokens = len(message_content) // 4

            if tokens_used + message_tokens <= max_tokens:
                context.append(message_content)
                tokens_used += message_tokens
            else:
                break
        except Exception as e:
            print(f"Error fetching reply chain message: {e}")
            break

    return context[::-1]

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content_lower = message.content.lower()
    if content_lower == '🐸':
        await message.channel.send(":frog:")
    elif content_lower == "uwu":
        await uwu.uwu(message)
    elif content_lower == "owo":
        await owo.owo(message)
    elif content_lower == "weeb":
        await message.channel.send('https://media1.tenor.com/m/rM6sdvGLYCMAAAAC/bonk.gif')
    elif ':coolfrog:' in content_lower:
        await message.channel.send('<:coolfrog:1168605051779031060>')
    elif any(keyword in content_lower for keyword in ['primary mod']):
        await message.channel.send(':eyes:')
    else:
        if bot.user.mentioned_in(message):
            content = message.content.replace(bot.user.mention, '').strip()
        if content:
            ctx = await bot.get_context(message)
            if ctx.valid:
                await bot.process_commands(message)
            else:
                current_time = datetime.now()
                last_request_time = user_request_times.get(message.author.id)

                if last_request_time and current_time - last_request_time < RATE_LIMIT:
                    try:
                        await message.reply("You are sending messages too quickly. Please wait a moment before trying again.")
                    except (HTTPException, NotFound):
                        await message.channel.send("Could not send rate limit message, the original message might have been deleted.")
                    return

                user_request_times[message.author.id] = current_time

                try:
                    placeholder_message = await message.reply('Generating Response...')
                except (HTTPException, NotFound):
                    await message.channel.send("Could not send placeholder response, the original message might have been deleted.")
                    return

                context = await fetch_reply_chain(message, max_tokens=4096)
                combined_messages = [{"role": "user", "content": msg} for msg in context] + [{"role": "user", "content": content}]

                response = await GPT.ask_gpt(combined_messages)
                
                try:
                    await placeholder_message.edit(content=response)
                except HTTPException:
                    await message.channel.send(response)
            return
        await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        pass
    else:
        print(f"An error occurred: {error}")

try:
    bot.run(TOKEN)
except Exception as e:
    print(f"An error occurred: {e}")
