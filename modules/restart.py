# modules.restart

from modules.utils.commons import is_admin_or_user
from discord.ext import commands
from pathlib import Path
import subprocess
import asyncio
import sys
import os

root_dir = Path(__file__).resolve().parent.parent
core_script = root_dir / 'core.py'

@commands.command(name="restart")
@is_admin_or_user()
async def restart_bot(ctx):
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

@commands.command(name="shutdown")
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

def setup(client):
    client.add_command(restart_bot)
    client.add_command(shutdown_bot)