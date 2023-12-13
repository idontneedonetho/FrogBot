# commands/update.py

from discord.ext import commands
import subprocess
print('Update.py loaded')

def is_admin_or_user(user_id=126123710435295232):
    async def predicate(ctx):
        is_admin = ctx.author.guild_permissions.administrator
        is_specific_user = ctx.author.id == user_id
        print(f"Admin check: {is_admin}, Specific user check: {is_specific_user}")
        return is_admin or is_specific_user
    return commands.check(predicate)

@commands.command(name="update")
@is_admin_or_user()
async def git_pull(ctx, branch="testing"):
    print('update command invoked')

    try:
        current_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()
        if current_branch != branch:
            await ctx.send(f"Switching to branch {branch}")
            subprocess.run(["git", "checkout", branch])

        await git_stash()

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

async def git_stash():
    try:
        print("Stashing changes...")
        subprocess.run(["git", "stash"])
        print("Changes stashed successfully.")
    except Exception as e:
        print(f"Error stashing changes: {e}")

def setup(bot):
    bot.add_command(git_pull)
