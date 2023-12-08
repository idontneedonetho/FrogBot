# commands/ping.py
from discord.ext import commands

@commands.command(name="frog")
async def frog(ctx):
    """Frog command that responds with :frog:"""
    await ctx.send(":frog:")
