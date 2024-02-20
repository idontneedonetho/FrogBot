# core.py

from modules.utils.commons import bot_version, is_admin_or_user
from modules.utils.GPT import process_message_with_llm
from modules.roles import check_user_points
from disnake.ext import commands
from dotenv import load_dotenv
import concurrent.futures
from pathlib import Path
import importlib.util
import subprocess
import traceback
import asyncio
import disnake
import sys
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
intents = disnake.Intents(
    members=True,
    guilds=True,
    messages=True,
    message_content=True,
    guild_messages=True,
    reactions=True
)

command_sync_flags = commands.CommandSyncFlags.default()
command_sync_flags.sync_commands_debug = True
client = commands.Bot(command_prefix='//', intents=intents, command_sync_flags=command_sync_flags, test_guilds=[1137853399715549214])

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

@client.slash_command(description = "Restart the bot.")
@is_admin_or_user()
async def restart(ctx):
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

@client.slash_command(description = "Shut down the bot.")
@is_admin_or_user()
async def shutdown(ctx: disnake.ApplicationCommandInteraction):
    await ctx.response.send_message(
        "Are you sure you want to shut down the bot?",
        components=[
            disnake.ui.Button(label="Yes", style=disnake.ButtonStyle.success, custom_id="shutdown_yes"),
            disnake.ui.Button(label="No", style=disnake.ButtonStyle.danger, custom_id="shutdown_no"),
        ],
    )

@client.listen("on_button_click")
async def shutdown_listener(inter: disnake.MessageInteraction):
    if inter.component.custom_id not in ["shutdown_yes", "shutdown_no"]:
        return

    if inter.component.custom_id == "shutdown_yes":
        await inter.response.send_message("Shutting down...")
        await inter.bot.close()
    elif inter.component.custom_id == "shutdown_no":
        await inter.response.send_message("Bot shutdown canceled.")

@client.slash_command(description = "Update the bot from the Git repository.")
@is_admin_or_user()
async def update(ctx, branch="beta"):
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

'''This code defines the core functionality of the bot, including event handlers for when the bot is ready, when a message is received, when a reaction is added, and when a command error occurs, as well as a method to process commands.'''
@client.event
async def on_ready():
    await check_user_points(client)
    await client.change_presence(activity=disnake.Game(name=f"@{client.user.name} help | {bot_version}"))
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

@client.event
async def on_message(message):
    if message.author == client.user or message.author.bot:
        return
    if client.user in message.mentions:
        await process_message_with_llm(message, client)
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

'''Kaofui was here uwu'''