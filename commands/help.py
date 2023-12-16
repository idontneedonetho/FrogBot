# commands/help.py

from discord.ext import commands

async def advanced_help(ctx):
    # Create the help function here
    help_message = ('>>> *For commands below, the user must have the admin privileges.*\n\n**"@FrogBot add [amount] points @user"** - Add points to a user.\n**"@FrogBot remove [amount] points @user"** - Remove points from a user.\n**"@FrogBot check points @user"** - Check points for a user.\n**"@FrogBot killbot"** - Shutdown the bot, needs confirmation.\n**"@FrogBot init_leaderboard"** - Initialize the leaderboard.')
    await ctx.send(f"{help_message}")
    
async def points_help(ctx):
    help_message = ('>>> Points work as follows:\n\n1,000 points - Tadpole Trekker\n2,500 points - Puddle Pioneer\n5,000 points - Jumping Junior\n10,000 points - Croaking Cadet\n25,000 points - Ribbit Ranger\n50,000 points - Frog Star\n100,000 points - Lily Legend\n250,000 points - Froggy Monarch\n500,000 points - Never Nourished Fat Frog\n1,000,000 points - Frog Daddy\n\nBug report = 250 points\nError log included += 250 points\nVideo included += 500 points\n\nFeature request = 100 points\nDetailed/thought out += 250 points\n\nSubmitting a PR = 1000 points\nPR gets merged += 2500 points\n\nHelping someone with a question = 100 points\n')
    await ctx.send(f"{help_message}")

# Example
#async def uwu_help(ctx):
#    help_message = (
#        "Learn the art of uwu with FrogBot!\n\n"
#        "`uwu` - Get a random uwu response."
#    )
#    await ctx.send(f"```{help_message}```")

async def custom_help_command(ctx, category=None):
    if category:
        # Invoke the corresponding help function based on the category
        if category.lower() == 'advanced':
            await advanced_help(ctx)
        elif category.lower() == 'points':
            await points_help(ctx)
        # Add more categories as needed
    else:
        general_help_message = ('>>> *Keywords for bot reactions will not be listed*\n\n**"@FrogBot [question]"** - Ask ChatGPT a question. This has a 15 second cooldown. To continue conversations, you must reply to the bots message.\n\n**"@FrogBot help points"** - Displays the points help message.\n**"@FrogBot check points"** - Check your points and rank.\n**":frog:"** - :frog:\n**"@FrogBot help"** - Display this help message.\n\n__*Commands below need Admin permissions*__\n**"@FrogBot help advanced"** - Displays advanced commands.')
        await ctx.send(f"{general_help_message}")

def setup(bot):
    bot.remove_command("help")
    bot.add_command(commands.Command(custom_help_command, name="help"))
