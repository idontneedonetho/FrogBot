# commands/update.py

from discord.ext import commands
from modules.utils.commons import is_admin_or_user
import subprocess

@commands.command(name="update")
@is_admin_or_user()
async def git_pull(ctx, branch="beta"):
    print('update command invoked')
    try:
        current_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()
        if current_branch != branch:
            await ctx.send(f"Switching to branch {branch}")
            subprocess.run(["git", "checkout", branch])
        await git_stash(ctx)
        process = subprocess.Popen(['git', 'pull', 'origin', branch], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()
        if process.returncode == 0:
            print('Git pull successful.')
            await ctx.send('Git pull successful.')
        else:
            print(f'Error updating the script: {error.decode()}')
            await ctx.send(f'Error updating the script: {error.decode()}')
    except Exception as e:
        print(f'Error updating the script: {e}')
        await ctx.send(f'Error updating the script: {e}')

async def git_stash(ctx):
    try:
        print("Stashing changes...")
        subprocess.run(["git", "stash"])
        print("Changes stashed successfully.")
        await ctx.send('Changes stashed successfully.')
    except Exception as e:
        print(f"Error stashing changes: {e}")
        await ctx.send(f"Error stashing changes: {e}")

def setup(client):
    client.add_command(git_pull)