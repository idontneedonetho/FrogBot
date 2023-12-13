# commands/restart.py

from discord.ext import commands
import subprocess
import sys
print('Restart.py loaded')

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
    print("Restarting bot...")

    with open(RESTART_FLAG_FILE, 'w') as file:
        file.write('restarting')

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
