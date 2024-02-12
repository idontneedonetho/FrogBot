# FrogBot/modules/help.py

from discord.ext import commands
from discord import Embed

async def advanced_help(ctx, bot_name):
    embed = Embed(
        title="Advanced Help", 
        description=f"*For commands below, the user must have admin privileges.*\nPrefix all commands with **\"@{bot_name}\"**", 
        color=0x00ff00
    )
    embed.add_field(name="--Multi-commands--", value=f"Multi-commands work as follows: **\"@{bot_name} [command 1]; [command 2]\"** etc.", inline=False)
    embed.add_field(name="whiteboard", value="Send a .txt file as a long message.", inline=False)
    embed.add_field(name="edit", value="Reply to the message you want to edit, include **\"edit\"** in your reply, and make sure to attach a .txt file.", inline=False)
    embed.add_field(name="restart", value="Restart the bot.", inline=False)
    embed.add_field(name="update", value="Update the bot.", inline=False)
    embed.add_field(name="add [amount] points @user", value="Add points to a user.", inline=False)
    embed.add_field(name="remove [amount] points @user", value="Remove points from a user.", inline=False)
    embed.add_field(name="check points @user", value="Check points for a user.", inline=False)
    embed.add_field(name="shutdown", value="Shutdown the bot, needs confirmation.", inline=False)
    await ctx.send(embed=embed)
    
async def points_help(ctx):
    embed = Embed(title="Points Help", description="Points work as follows:", color=0x00ff00)
    embed.add_field(name="Tadpole Trekker", value="1,000 points", inline=True)
    embed.add_field(name="Puddle Pioneer", value="2,500 points", inline=True)
    embed.add_field(name="Jumping Junior", value="5,000 points", inline=True)
    embed.add_field(name="Croaking Cadet", value="10,000 points", inline=True)
    embed.add_field(name="Ribbit Ranger", value="25,000 points", inline=True)
    embed.add_field(name="Frog Star", value="50,000 points", inline=True)
    embed.add_field(name="Lily Legend", value="100,000 points", inline=True)
    embed.add_field(name="Froggy Monarch", value="250,000 points", inline=True)
    embed.add_field(name="Never Nourished Fat Frog", value="500,000 points", inline=True)
    embed.add_field(name="Frog Daddy", value="1,000,000 points", inline=True)
    embed.add_field(name="--------", value="\u200b", inline=False)
    embed.add_field(name="Bug report", value="250 points", inline=True)
    embed.add_field(name="Error log included", value="+= 250 points", inline=True)
    embed.add_field(name="Video included", value="+= 500 points", inline=True)
    embed.add_field(name="Feature request", value="100 points", inline=True)
    embed.add_field(name="Detailed/thought out", value="+= 250 points", inline=True)
    embed.add_field(name="Submitting a PR", value="1000 points", inline=True)
    embed.add_field(name="PR gets merged", value="+= 2500 points", inline=True)
    embed.add_field(name="Helping someone with a question", value="100 points", inline=True)
    await ctx.send(embed=embed)

async def general_help(ctx, bot_name):
    embed = Embed(title="General Help", description=f"*Keywords for bot reactions will not be listed*\n\nPrefix all commands with **\"@{bot_name}\"**", color=0x00ff00)
    embed.add_field(name="[question]", value="Ask ChatGPT a question. To continue conversations, you must reply to the bot's message.", inline=False)
    embed.add_field(name="help points", value="Displays the points help message.", inline=False)
    embed.add_field(name="check points", value="Check your points and rank.", inline=False)
    embed.add_field(name="ttt_start @[user 1] @[user 2]", value="Initiates a game of Tic-Tac-Toe between User 1 and User 2. User 1, tagged first, will play as 'X' and make the first move. User 2, tagged second, will play as 'O'. If the bot is tagged, you will play against it.", inline=False)
    embed.add_field(name="help", value="Display this help message.", inline=False)
    embed.add_field(name="--------", value="", inline=False)
    embed.add_field(name="*Commands below need Admin permissions*", value="", inline=False)
    embed.add_field(name="help advanced", value="Displays advanced commands.", inline=False)
    await ctx.send(embed=embed)

async def custom_help_command(ctx, category=None):
    bot_name = ctx.me.display_name  # Get the bot's display name
    if category:
        if category.lower() == 'advanced':
            await advanced_help(ctx, bot_name)
        elif category.lower() == 'points':
            await points_help(ctx)
        # Add more categories as needed
    else:
        await general_help(ctx, bot_name)

def setup(client):
    client.remove_command("help")
    client.add_command(commands.Command(custom_help_command, name="help"))
