# core.py

import discord
import copy
import os
import traceback
from discord.ext import commands
from dotenv import load_dotenv
from module_loader import ModuleLoader
from modules.roles import check_user_points
from modules.utils.commons import frog_version
from modules.utils.GPT import process_message_with_llm
load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True
intents.guild_messages = True
intents.reactions = True
client = commands.Bot(command_prefix=commands.when_mentioned, intents=intents, case_insensitive=True)

module_loader = ModuleLoader('modules')
module_loader.load_modules(client)

try:  
    from modules.utils.memory_check import MemoryMonitor
    memory_monitor = MemoryMonitor(interval=60)
except Exception as e:
    pass

@client.event
async def on_ready():
    await check_user_points(client)
    await client.change_presence(activity=discord.Game(name=f"@FrogBot help | {frog_version}"))
    print(f'Logged in as {client.user.name}')
    try:
        with open("restart_channel_id.txt", "r") as file:
            channel_id = int(file.read().strip())
            channel = client.get_channel(channel_id)
            if channel:
                await channel.send("I'm back online!")
            os.remove("restart_channel_id.txt")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Error sending restart message: {e}")

async def is_valid_command(message, command_text):
    temp_message = copy.copy(message)
    temp_message.content = command_text
    ctx = await client.get_context(temp_message)
    return ctx.command is not None

async def process_commands_sequentially(message, command_texts):
    for command_text in command_texts:
        message.content = command_text
        ctx = await client.get_context(message)
        if ctx.valid:
            await client.invoke(ctx)
        else:
            await process_message_with_llm(message, client)
            
@client.event
async def on_message(message):
    if message.author == client.user or message.author.bot:
        return
    processed_as_query = False
    if client.user.mentioned_in(message):
        command_texts = [command.strip() for command in message.content.split(';')]
        processed_commands = False
        for command_text in command_texts:
            if not command_text.startswith(f'<@!{client.user.id}>') and not command_text.startswith(f'<@{client.user.id}>'):
                command_text = f'<@!{client.user.id}> {command_text}'
            if await is_valid_command(message, command_text):
                await process_commands_sequentially(message, [command_text])
                processed_commands = True
            else:
                if not processed_commands:
                    await process_message_with_llm(message, client)
                    processed_as_query = True
                    break
    if not processed_commands and not processed_as_query:
        await client.process_commands(message)

@client.event
async def on_reaction_add(reaction, user):
    for handler in module_loader.get_event_handlers('on_reaction_add'):
        await handler(reaction, user)

@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Sorry, I didn't understand that command.")
    else:
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        tb_str = "".join(tb)
        print(f'An error occurred: {error}\n{tb_str}')

try:
    client.run(os.getenv("DISCORD_TOKEN"))
finally:
    memory_monitor.stop()
    print("Memory monitor stopped")