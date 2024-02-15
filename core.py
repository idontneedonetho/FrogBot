# core.py

from modules.utils.commons import frog_version, is_admin_or_user
from modules.utils.GPT import process_message_with_llm
from modules.roles import check_user_points
from discord.ext import commands
from dotenv import load_dotenv
import concurrent.futures
from pathlib import Path
import importlib.util
import subprocess
import traceback
import asyncio
import discord
import copy
import sys
import re
import os

load_dotenv()

'''This Python class, ModuleLoader, dynamically loads Python modules from a specified directory, excluding 'utils', and provides methods to retrieve command and event handlers from these modules.'''
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

'''This Python code initializes a Discord bot with specific intents, and uses the ModuleLoader instance to dynamically load modules from the 'modules' directory into the bot.'''
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

'''This code defines commands for the bot to restart, shutdown, and update itself, including switching branches and pulling from a Git repository, with error handling for each operation.'''
root_dir = Path(__file__).resolve().parent
core_script = root_dir / 'core.py'

@client.command(name="restart")
@is_admin_or_user()
async def restart_bot(ctx):
    try:
        await ctx.send("Restarting bot, please wait...")
        with open("restart_channel_id.txt", "w") as file:
            file.write(str(ctx.channel.id))
        for cmd in list(ctx.bot.all_commands.keys()):
            ctx.bot.remove_command(cmd)
        await asyncio.sleep(3)
        subprocess.Popen([sys.executable, str(core_script)])
        await asyncio.sleep(2)
        await ctx.bot.close()
        os._exit(0)
    except PermissionError:
        await ctx.send("Bot does not have permission to perform the restart operation.")
    except FileNotFoundError:
        await ctx.send("Could not find the core.py script.")
    except Exception as e:
        await ctx.send(f"An error occurred while trying to restart the bot: {e}")

@client.command(name="shutdown")
@is_admin_or_user()
async def shutdown_bot(ctx):
    confirmation_message = await ctx.send("Are you sure you want to shut down the bot? React with ✅ to confirm.")
    await confirmation_message.add_reaction("✅")
    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) == '✅' and reaction.message.id == confirmation_message.id
    try:
        await ctx.bot.wait_for('reaction_add', timeout=60.0, check=check)
        await ctx.send("Shutting down...")
        await ctx.bot.close()
    except asyncio.TimeoutError:
        await ctx.send("Bot shutdown canceled.")

@client.command(name="update")
@is_admin_or_user()
async def git_pull(ctx, branch="beta"):
    try:
        await switch_branch(ctx, branch)
        await git_stash(ctx)
        await git_pull_origin(ctx, branch)
    except Exception as e:
        await ctx.send(f'Error updating the script: {e}')

async def switch_branch(ctx, branch):
    current_branch_proc = await asyncio.create_subprocess_exec(
        "git", "rev-parse", "--abbrev-ref", "HEAD",
        stdout=asyncio.subprocess.PIPE)
    stdout, _ = await current_branch_proc.communicate()
    current_branch = stdout.decode().strip()
    if current_branch != branch:
        await ctx.send(f"Switching to branch {branch}")
        await asyncio.create_subprocess_exec("git", "checkout", branch)

async def git_stash(ctx):
    stash_proc = await asyncio.create_subprocess_exec("git", "stash")
    await stash_proc.communicate()
    await ctx.send('Changes stashed successfully.')

async def git_pull_origin(ctx, branch):
    pull_proc = await asyncio.create_subprocess_exec(
        'git', 'pull', 'origin', branch,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await pull_proc.communicate()
    if pull_proc.returncode == 0:
        await ctx.send('Git pull successful.')
    else:
        raise Exception(stderr.decode())

def setup(client):
    client.add_command(restart_bot)
    client.add_command(shutdown_bot)
    client.add_command(git_pull)

'''This code defines the core functionality of the bot, including event handlers for when the bot is ready, when a message is received, when a reaction is added, and when a command error occurs, as well as a method to process commands.'''
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

executor = concurrent.futures.ThreadPoolExecutor(max_workers=min(os.cpu_count(), 4))

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
        if command in ['restart', 'shutdown', 'update'] + list(client.all_commands.keys()):
            command_texts = re.split(r';(?=(?:[^`]*`[^`]*`)*[^`]*$)', message.content)
        else:
            command_texts = [message.content]
        for command_text in command_texts:
            command_text = command_text.strip()
            if not command_text.startswith(f'<@!{client.user.id}>') and not command_text.startswith(f'<@{client.user.id}>'):
                command_text = f'<@!{client.user.id}> {command_text}'
            executor.submit(await process_commands(message, [command_text]))
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

'''This code attempts to run the Discord client with a token retrieved from the environment variables.'''
try:
    client.run(os.getenv("DISCORD_TOKEN"))
finally:
    memory_monitor.stop()
    print("Memory monitor stopped")