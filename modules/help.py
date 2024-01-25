# FrogBot/modules/help.py

from discord.ext import commands

async def advanced_help(ctx):
    help_message = (
        '>>> *For commands below, the user must have admin privileges.*\n\n'
        '**"@FrogBot add [amount] points @user"** - Add points to a user.\n'
        '**"@FrogBot remove [amount] points @user"** - Remove points from a user.\n'
        '**"@FrogBot check points @user"** - Check points for a user.\n'
        '**"@FrogBot shutdown"** - Shutdown the bot, needs confirmation.\n'
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
    if category:
        if category.lower() == 'advanced':
            await advanced_help(ctx)
        elif category.lower() == 'points':
            await points_help(ctx)
        # Add more categories as needed
    else:
        general_help_message = (
            '>>> *Keywords for bot reactions will not be listed*\n\n'
            '**"@FrogBot [question]"** - Ask ChatGPT a question. This has a 15 second cooldown. '
            'To continue conversations, you must reply to the bot\'s message.\n\n'
            '**"@FrogBot help points"** - Displays the points help message.\n'
            '**"@FrogBot check points"** - Check your points and rank.\n'
            '**":frog:"** - :frog:\n'
            '**"@FrogBot help"** - Display this help message.\n\n'
            '__*Commands below need Admin permissions*__\n'
            '**"@FrogBot help advanced"** - Displays advanced commands.'
        )
        await ctx.send(general_help_message)

def setup(bot):
    bot.remove_command("help")
    bot.add_command(commands.Command(custom_help_command, name="help"))
