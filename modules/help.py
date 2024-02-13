# modules.help

from discord.ext import commands

async def advanced_help(ctx, bot_name):
    help_message = (
        ">>> **Advanced Help**\n"
        "*For commands below, the user must have admin privileges.*\n"
        f"Prefix all commands with **\"@{bot_name}\"**\n"
        f"Multi-commands work as follows: **\"@{bot_name} [command 1]; [command 2]\"** etc. Each command must be separated by ';'.\n\n"
        "**whiteboard**\n"
        "Send a .txt file as a long message.\n\n"
        "**edit**\n"
        "__*Can only be used while replying to the original whiteboard message*__, make sure to attach a .txt file.\n\n"
        "**restart**\n"
        "Restart the bot.\n\n"
        "**update**\n"
        "Update the bot.\n\n"
        "**add [amount] points @user**\n"
        "Add points to a user.\n\n"
        "**remove [amount] points @user**\n"
        "Remove points from a user.\n\n"
        "**check points @user**\n"
        "Check points for a user.\n\n"
        "**shutdown**\n"
        "Shutdown the bot, needs confirmation.\n"
    )
    await ctx.send(help_message)

async def points_help(ctx):
    help_message = (
        '>>> **Points work as follows:**\n\n'
        '1,000 points - Tadpole Trekker\n'
        '2,500 points - Puddle Pioneer\n'
        '5,000 points - Jumping Junior\n'
        '10,000 points - Croaking Cadet\n'
        '25,000 points - Ribbit Ranger\n'
        '50,000 points - Frog Star\n'
        '100,000 points - Lily Legend\n'
        '250,000 points - Froggy Monarch\n'
        '500,000 points - Never Nourished Fat Frog\n'
        '1,000,000 points - Frog Daddy\n\n'
        'Bug report = 250 points\n'
        'Error log included = 250 points\n'
        'Video included = 500 points\n\n'
        'Feature request = 100 points\n'
        'Detailed/thought out = 250 points\n\n'
        'Testing a PR/feature = 1000 points\n'
        'Submitting a PR = 1000 points\n'
        'PR gets merged = 2500 points\n\n'
        'Helping someone with a question = 100 points\n'
    )
    await ctx.send(help_message)

async def general_help(ctx, bot_name):
    help_message = (
        ">>> **General Help**\n"
        "*Keywords for bot reactions will not be listed*\n"
        f"Prefix all commands with **\"@{bot_name}\"**\n\n"
        "**[question]**\n"
        "Ask ChatGPT a question. To continue conversations, you must reply to the bot's message.\n\n"
        "**help points**\n"
        "Displays the points help message.\n\n"
        "**check points**\n"
        "Check your points and rank.\n\n"
        "**ttt_start @[user 1] @[user 2]**\n"
        "Initiates a game of Tic-Tac-Toe between User 1 and User 2. User 1, tagged first, will play as 'X' and make the first move. User 2, tagged second, will play as 'O'. If the bot is tagged, you will play against it.\n\n"
        "**help**\n"
        "Display this help message.\n\n"
        "--------\n\n"
        "*Commands below need Admin permissions*\n\n"
        "**help advanced**\n"
        "Displays advanced commands.\n"
    )
    await ctx.send(help_message)

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
