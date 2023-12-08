# commands/help.py
from discord.ext import commands

async def points_help(ctx):
    # Create the help function here
    help_message = ('>>> *For commands below, the user must have the admin privileges.*\n\n**"@FrogBot add [amount] points @user"** - Add points to a user.\n**"@FrogBot remove [amount] points @user"** - Remove points from a user.\n**"@FrogBot check points @user"** - Check points for a user.')
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
        if category.lower() == 'points':
            await points_help(ctx)
        # Add more categories as needed
    else:
        general_help_message = ('>>> *Keywords for bot reactions will not be listed*\n\n**"@FrogBot my points"** - Check your points and rank.\n**"@FrogBot frog"** - :frog:.\n**"@FrogBot help"** - Display this help message.')
        await ctx.send(f"{general_help_message}")

def setup(bot):
    bot.remove_command("help")
    bot.add_command(commands.Command(custom_help_command, name="help"))
