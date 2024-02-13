# modules.update

from modules.utils.commons import is_admin_or_user
from discord.ext import commands
import asyncio

@commands.command(name="update")
@is_admin_or_user()
async def git_pull(ctx, branch="beta"):
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

def setup(client):
    client.add_command(git_pull)