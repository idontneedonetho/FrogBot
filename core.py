# core.py

from modules.utils.GPT import process_message_with_llm
from modules.utils.commons import frog_version
from modules.roles import check_user_points
from discord.ext import commands
from dotenv import load_dotenv
import importlib.util
import traceback
import discord
import copy
import re
import os

load_dotenv()

class ModuleLoader:
    def __init__(self, directory):
        self.directory = directory
        self.modules = []

    def load_modules(self, client):
        for root, dirs, files in os.walk(self.directory):
            if 'utils' in dirs:
                dirs.remove('utils')
            for filename in files:
                if filename.endswith('.py'):
                    module_name = filename[:-3]
                    module_path = os.path.join(root, filename)
                    try:
                        module = self._load_module(module_name, module_path)
                        self.modules.append(module)
                        print(f"Loading module: {module_name}")
                        if hasattr(module, 'setup'):
                            module.setup(client)
                    except Exception as e:
                        print(f"Failed to load module: {module_name}. Error: {e}")
                        continue

    def _load_module(self, module_name, module_path):
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def get_command_handlers(self):
        return {command: getattr(module, handler_name) 
                for module in self.modules if hasattr(module, 'cmd') 
                for command, handler_name in module.cmd.items() 
                if hasattr(module, handler_name)}

    def get_event_handlers(self, event_name):
        return [getattr(module, event_name) 
                for module in self.modules if hasattr(module, event_name)]

intents = discord.Intents(
    members=True,
    guilds=True,
    messages=True,
    message_content=True,
    guild_messages=True,
    reactions=True
)
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
    await client.change_presence(activity=discord.Game(name=f"@{client.user.name} help | {frog_version}"))
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

async def process_commands(message, command_texts):
    for command_text in command_texts:
        temp_message = copy.copy(message)
        temp_message.content = command_text
        ctx = await client.get_context(temp_message)
        if ctx.command is not None:
            await client.invoke(ctx)
        else:
            await process_message_with_llm(temp_message, client)

@client.event
async def on_message(message):
    if message.author == client.user or message.author.bot:
        return
    if client.user.mentioned_in(message):
        command = message.content.split()[1] if len(message.content.split()) > 1 else ''
        if command in client.all_commands:
            command_texts = re.split(r';(?=(?:[^`]*`[^`]*`)*[^`]*$)', message.content)
        else:
            command_texts = [message.content]
        for command_text in command_texts:
            command_text = command_text.strip()
            if not command_text.startswith(f'<@!{client.user.id}>') and not command_text.startswith(f'<@{client.user.id}>'):
                command_text = f'<@!{client.user.id}> {command_text}'
            await process_commands(message, [command_text])
    else:
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