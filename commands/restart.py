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

    # Get the command used to run the script
    command = [sys.executable, "bot.py"]  # Assuming your main script is named bot.py

    try:
        # Start a new Python process
        subprocess.Popen(command, close_fds=True)

        # You can add a response to the context if needed
        await ctx.send("Bot restarting...")

        # Close the current event loop
        await ctx.bot.close()

        # Terminate the current process
        sys.exit()

    except SystemExit:
        pass  # Ignore the SystemExit exception

    except Exception as e:
        print(f"Error restarting the bot: {e}")

def setup(bot):
    bot.add_command(restart_bot)
