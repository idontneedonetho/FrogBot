# commands/restart.py

from discord.ext import commands
import subprocess
import sys
print('Restart.py loaded')

def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

@commands.command(name="restart")
@commands.check(is_admin())
async def restart_bot(ctx):
    print("Restarting bot...")

    command = [sys.executable, "bot.py"]

    try:
        subprocess.Popen(command, close_fds=True)
        await ctx.send("Bot restarting...")
        await ctx.bot.close()
        sys.exit()

    except SystemExit:
        pass

    except Exception as e:
        print(f"Error restarting the bot: {e}")

def setup(bot):
    bot.add_command(restart_bot)
