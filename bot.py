frog_version = "v2"
import discord
import asyncio
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os

from commands import uwu, owo, help, points, leaderboard

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise ValueError("Bot token not found in .env file. Please add it.")

intents = discord.Intents.all()
client = discord.Client(intents=intents)

user_points = points.initialize_points_database()

bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents, case_insensitive=True)

# Add-ons
points.setup(bot)
help.setup(bot)
leaderboard.setup(bot)

last_used_responses = {"uwu": None, "owo": None}

@bot.event
async def on_ready():
    print(f"Ready {bot.user.name}")
    await bot.change_presence(activity=discord.Game(name=f"version {frog_version}"))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content.lower()

    # Reactions
    if message.content == "uwu":
        await uwu.uwu(message)
    elif message.content == "owo":
        await owo.owo(message)
    elif message.content.lower() == "weeb":
        await message.channel.send('https://media1.tenor.com/m/rM6sdvGLYCMAAAAC/bonk.gif')
    elif ':coolfrog:' in message.content:
        await message.channel.send('<:coolfrog:1168605051779031060>')
    
    await bot.process_commands(message)

# Commands
@bot.command(name="frog")
async def frog(ctx):
    await ctx.send(":frog:")

bot.run(TOKEN)
