# bot.py

frog_version = "v2 beta 4"
import discord
import asyncio
import subprocess
import sys
from discord.ext import commands, tasks
from dotenv import load_dotenv
import importlib
from datetime import datetime, timedelta
from discord.errors import HTTPException, NotFound
import os

user_request_times = {}
gpt_semaphore = asyncio.Semaphore(1)
RESTART_FLAG_FILE = 'restart.flag'
RATE_LIMIT = timedelta(seconds=5)

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

modules = [
    "GPT", 
    "help", 
    "points", 
    "leaderboard", 
    "emoji", 
    "roles", 
    "update", 
    "restart"
]

for module_name in modules:
    try:
        mod = importlib.import_module(f'commands.{module_name}')
        globals()[module_name] = mod
        if hasattr(mod, 'setup'):
            mod.setup(bot)
        print(f"Successfully imported and set up {module_name}")
    except ImportError as e:
        print(f"Error importing {module_name}: {e}")
    except Exception as e:
        print(f"Error setting up {module_name}: {e}")

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

    current_prompt_tokens = len(message.content) // 4
    max_tokens -= current_prompt_tokens

    while message.reference is not None and tokens_used < max_tokens:
        try:
            message = await message.channel.fetch_message(message.reference.message_id)
            message_content = f"{message.author.display_name}: {message.content}"
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
    content = None
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
                        await message.channel.send("Could not send the rate limit message; the original message might have been deleted.")
                    return

                user_request_times[message.author.id] = current_time

                async with message.channel.typing():
                    context = await fetch_reply_chain(message, max_tokens=4096)
                    combined_messages = [{"role": "user", "content": msg} for msg in context] + [{"role": "user", "content": content}]
                    
                    async with gpt_semaphore:
                        response = await GPT.ask_gpt(combined_messages)

                    max_length = 2000
                    if len(response) > max_length:
                        parts = []
                        while len(response) > max_length:
                            split_index = response.rfind(' ', 0, max_length)
                            if split_index == -1:
                                split_index = max_length
                            parts.append(response[:split_index])
                            response = response[split_index:].strip()
                        parts.append(response)
                        for part in parts:
                            try:
                                await message.reply(part)
                            except discord.HTTPException:
                                await message.channel.send(part)
                            await asyncio.sleep(1)
                    else:
                        try:
                            await message.reply(response)
                        except discord.HTTPException:
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
    if __name__ == "__main__":
        subprocess.Popen([sys.executable, 'commands/watchdog.py'])
        bot.run(TOKEN)
except Exception as e:
    print(f"An error occurred: {e}")
