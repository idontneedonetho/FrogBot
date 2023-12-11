# commands/update.py

from discord.ext import commands
import subprocess
print('Update.py loaded')

def is_admin_or_user(user_id=126123710435295232):
    async def predicate(ctx):
        author_id = ctx.author.id
        return ctx.author.guild_permissions.administrator or author_id == user_id
    return commands.check(predicate)

@commands.command(name="update")
@commands.check(is_admin_or_user())
async def git_pull(ctx):
    print('update command invoked')
    repo_url = 'https://github.com/idontneedonetho/FrogBot.git'

    try:
        await git_stash()
        process = subprocess.Popen(['git', 'pull', repo_url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
