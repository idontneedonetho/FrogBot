# FrogBot/modules/help.py

from discord.ext import commands

async def advanced_help(ctx, bot_name):
    help_message = (
        f'>>> *For commands below, the user must have admin privileges.*\n\n'
        f'**"@{bot_name} add [amount] points @user"** - Add points to a user.\n'
        f'**"@{bot_name} remove [amount] points @user"** - Remove points from a user.\n'
        f'**"@{bot_name} check points @user"** - Check points for a user.\n'
        f'**"@{bot_name} shutdown"** - Shutdown the bot, needs confirmation.\n'
    )
    await ctx.send(help_message)
    
async def points_help(ctx):
    help_message = (
        '>>> Points work as follows:\n\n'
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
        'Error log included += 250 points\n'
        'Video included += 500 points\n\n'
        'Feature request = 100 points\n'
        'Detailed/thought out += 250 points\n\n'
        'Submitting a PR = 1000 points\n'
        'PR gets merged += 2500 points\n\n'
        'Helping someone with a question = 100 points\n'
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
        general_help_message = (f'>>> *Keywords for bot reactions will not be listed*\n\n'
            f'**"@{bot_name} [question]"** - Ask ChatGPT a question.\n'
            'To continue conversations, you must reply to the bot\'s message.\n\n'
            f'**"@{bot_name} help points"** - Displays the points help message.\n'
            f'**"@{bot_name} check points"** - Check your points and rank.\n'
            f'**"@{bot_name} ttt_start @[user 1] @[user 2]"** - Start a game of Tic-Tac-Toe.\n'
            f'**"@{bot_name} help"** - Display this help message.\n\n'
            '__*Commands below need Admin permissions*__\n'
            f'**"@{bot_name} help advanced"** - Displays advanced commands.'
        )
        await ctx.send(general_help_message)

def setup(client):
    client.remove_command("help")
    client.add_command(commands.Command(custom_help_command, name="help"))
