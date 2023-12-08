# commands/ping.py
from discord.ext import commands

@commands.command(name="frog")
async def ping(ctx):
    """Frog command."""
    await ctx.send(":frog:")
