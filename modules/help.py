# modules.help


from disnake import Option, OptionType, OptionChoice
from disnake.ext import commands

@commands.slash_command(
    description="Shows help information",
    options=[
        Option(
            name="category",
            description="The category of help you want",
            type=OptionType.string,
            required=False,
            choices=[
                OptionChoice(name="Points", value="points"),
                OptionChoice(name="General", value="general"),
                OptionChoice(name="Advanced", value="advanced")
            ]
        )
    ]
)
async def help(ctx, category: str = "general"):
    bot_name = ctx.me.display_name
    if category.lower() == "points":
        await points_help(ctx)
    elif category.lower() == "advanced":
        await advanced_help(ctx)
    else:
        await general_help(ctx, bot_name)

async def advanced_help(ctx):
    help_message = (
        ">>> **Advanced Help**\n"
        "*For commands below, the user must have admin privileges.*\n\n"
        "**whiteboard**\n"
        "Put your message inside of a code block, and it'll post that message.\n\n"
        "**edit**\n"
        "__*Include the original message ID before the codeblock*__, make sure the edited or new message is inside a codeblock.\n\n"
        "**restart**\n"
        "Restart the bot.\n\n"
        "**update**\n"
        "Update the bot.\n\n"
        "**add [amount] [user]**\n"
        "Add points to a user.\n\n"
        "**remove [amount] [user]**\n"
        "Remove points from a user.\n\n"
        "**check points [user]**\n"
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
        "*Keywords for bot reactions will not be listed*\n\n"
        f"**\"@{bot_name}\" [question]**\n"
        "Ask ChatGPT a question. To continue conversations, you must reply to the bot's message.\n\n"
        "**help points**\n"
        "Displays the points help message.\n\n"
        "**check_points**\n"
        "Check your points and rank.\n\n"
        "**tictactoe**\n"
        "Initiates a game of Tic-Tac-Toe between User 1 and User 2. If the bot is tagged, you will play against it.\n\n"
        "**help**\n"
        "Display this help message.\n\n"
        "--------\n\n"
        "*Commands below need Admin permissions*\n\n"
        "**help advanced**\n"
        "Displays advanced commands.\n"
    )
    await ctx.send(help_message)

def setup(client):
    client.add_slash_command(help)