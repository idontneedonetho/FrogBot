# FrogBot/modules/restart.py

from discord.ext import commands
import subprocess
import asyncio
import os
import sys
from pathlib import Path
from modules.utils.commons import is_admin_or_user

current_dir = Path(__file__).resolve().parent
root_dir = current_dir.parent
core_script = root_dir / 'core.py'

@commands.command(name="restart")
@is_admin_or_user()
async def restart_bot(ctx):
    await ctx.send("Restarting bot, please wait...")
    if os.path.exists("restart_channel_id.txt"):
        os.remove("restart_channel_id.txt")
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

def setup(bot):
    bot.add_command(restart_bot)
    bot.add_command(shutdown_bot)
