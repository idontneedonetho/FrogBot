# commands/restart.py

from discord.ext import commands
import subprocess
import sys
import asyncio
import os

WATCHDOG_PID_FILE = '../watchdog.pid'
RESTART_FLAG_FILE = 'restart.flag'

def is_admin_or_user(user_id=126123710435295232):
    async def predicate(ctx):
        is_admin = ctx.author.guild_permissions.administrator
        is_specific_user = ctx.author.id == user_id
        print(f"Admin check: {is_admin}, Specific user check: {is_specific_user}")
        return is_admin or is_specific_user
    return commands.check(predicate)

@commands.command(name="restart")
@is_admin_or_user()
async def restart_bot(ctx):
    try:
        await ctx.send("Restarting bot, this may take up to a minute...")
        with open(RESTART_FLAG_FILE, 'w') as file:
            file.write('restarting')
        await ctx.bot.close()
    except Exception as e:
        await ctx.send(f"Error occurred while restarting: {e}")
        print(f"Error restarting the bot: {e}")

@commands.command(name="killbot")
@is_admin_or_user()
async def kill_bot(ctx):
    confirmation_message = await ctx.send("Are you sure you want to shut down the bot? React with ✅ to confirm.")

    await confirmation_message.add_reaction("✅")

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) == '✅' and reaction.message.id == confirmation_message.id

    try:
        await ctx.bot.wait_for('reaction_add', timeout=60.0, check=check)
        await ctx.send("Shutting down...")
        await ctx.bot.close()
        if os.path.exists(WATCHDOG_PID_FILE):
            with open(WATCHDOG_PID_FILE, 'r') as pid_file:
                watchdog_pid = int(pid_file.read())
                os.kill(watchdog_pid, signal.SIGTERM)
    except asyncio.TimeoutError:
        await ctx.send("Bot shutdown canceled.")
            
def setup(bot):
    bot.add_command(restart_bot)
    bot.add_command(kill_bot)
