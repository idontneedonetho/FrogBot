# modules.help

from disnake import Embed, ButtonStyle
from disnake.ui import View, Button
from disnake.ext import commands
import logging

class HelpView(View):
    def __init__(self, cog, current_page):
        super().__init__(timeout=300)
        if current_page != "general":
            self.add_item(Button(label="General", style=ButtonStyle.primary, custom_id="help_general"))
        if current_page != "points":
            self.add_item(Button(label="Points", style=ButtonStyle.primary, custom_id="help_points"))
        if current_page != "advanced":
            self.add_item(Button(label="Advanced", style=ButtonStyle.primary, custom_id="help_advanced"))
        self.cog = cog

    async def interaction_check(self, inter) -> bool:
        try:
            await inter.response.defer()
            if inter.component.custom_id == "help_general":
                await self.cog.general_help(inter, inter.guild.me.display_name)
            elif inter.component.custom_id == "help_points":
                await self.cog.points_help(inter)
            elif inter.component.custom_id == "help_advanced":
                await self.cog.advanced_help(inter, inter.guild.me.display_name)
            return True
        except Exception as e:
            logging.error(f"Error in help interaction: {e}")
            if not inter.response.is_done():
                await inter.response.send_message(content="An error occurred while processing your request.", ephemeral=True)
            return False

class HelpCog(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.slash_command(description="Shows help information")
    async def help(self, inter):
        await inter.response.defer()
        bot_name = inter.guild.me.display_name
        await self.general_help(inter, bot_name)

    async def advanced_help(self, inter, bot_name):
        embed = Embed(
            title="Advanced Help",
            description=(
                "### *Admin permissions are required*\n\n"
                "--------\n\n"
                "**/control_panel**\n"
                "Open's a control panel that allows you to manage the bot.\n\n"
                "**/whiteboard**\n"
                "Open's a whiteboard that users can type in. You can edit messages sent by whiteboard by copying the message ID and pasting it in the Message ID field.\n\n"
                "**/translate thread [enable/disable/status]**\n"
                "Enable, disable, or check auto-translation status for the current thread.\n\n"
                "**/translate usage [view/reset]**\n"
                "View or reset your language usage statistics.\n\n"
                "**/restart**\n"
                f"Restart {bot_name}.\n\n"
                "**/update**\n"
                f"Update {bot_name}.\n\n"
                "**/add [amount] [user]**\n"
                "Add points to a user.\n\n"
                "**/remove [amount] [user]**\n"
                "Remove points from a user.\n\n"
                "**/check_points [user]**\n"
                "Check points for a user.\n\n"
                "**/shutdown**\n"
                f"Shutdown {bot_name}, needs confirmation.\n\n"
                "**/backup**\n"
                "Force backup the database. Automatically done at midnight UTC daily.\n\n"
            )
        )
        await inter.edit_original_message(embed=embed, view=self.get_help_view("advanced"))

    async def points_help(self, inter):
        embed = Embed(
            title="Points Help",
            description=(
                '### *Points work as follows:*\n\n'
                "--------\n"
                '__**Ranking System:**__\n'
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
                "--------\n"
                '__**Earning Points:**__\n'
                'Bug report = 250 points\n'
                'Error log included = 250 points\n'
                'Video included = 500 points\n\n'
                'Feature request = 100 points\n'
                'Detailed/thought out = 250 points\n\n'
                'Testing a PR/feature = 1000 points\n'
                'Submitting a PR = 1000 points\n'
                'PR gets merged = 3500 points\n\n'
                'Helping someone with a question = 100 points\n\n'
                "--------\n\n"
                "*Points are subject to change.*\n\n"
            )
        )
        await inter.edit_original_message(embed=embed, view=self.get_help_view("points"))

    async def general_help(self, inter, bot_name):
        embed = Embed(
            title="General Help",
            description=(
                "### *Keywords for bot reactions will not be listed*\n\n"
                "--------\n\n"
                "**/check_points**\n"
                "Check your points and rank.\n\n"
                "**/translate message**\n"
                "Translate text to another language.\n\n"
                "**/tictactoe**\n"
                f"Initiates a game of Tic-Tac-Toe between User 1 and User 2. If {bot_name} is tagged, you will play against it.\n\n"
                "**/help**\n"
                "Display this help message.\n\n"
                "--------\n\n"
                "*Advanced commands need Admin permissions*\n\n"
            )
        )
        await inter.edit_original_message(embed=embed, view=self.get_help_view("general"))

    def get_help_view(self, current_page):
        return HelpView(self, current_page)

def setup(client):
    client.add_cog(HelpCog(client))