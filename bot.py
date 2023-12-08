#testing v2
import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

if TOKEN is None:
    raise ValueError("Bot token not found in .env file. Please add it.")

bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"))

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user.name}")

# Load command modules
bot.load_extension("commands.ping")

bot.run(TOKEN)
