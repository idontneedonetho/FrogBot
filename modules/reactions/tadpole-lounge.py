# modules.reactions.tadpole-lounge

from datetime import datetime, timezone
from disnake.ext import commands
import disnake

ROLE_NAME = "tadpole"
CHANNEL_ID = 1208256502645657611

class TadpoleLoungeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def add_role(self, member: disnake.Member, role: disnake.Role, channel: disnake.TextChannel) -> None:
        if role:
            await member.add_roles(role)
            if channel:
                await channel.send(
                    f"Welcome {member.mention} to {member.guild.name}! You have been assigned the {role.mention} role. "
                    "Please read the rules and enjoy your stay! You'll gain full server access shortly. If you have any questions, feel free to ask here."
                )

    @commands.Cog.listener()
    async def on_member_join(self, member: disnake.Member) -> None:
        if member:
            role = disnake.utils.get(member.guild.roles, name=ROLE_NAME)
            channel = member.guild.get_channel(CHANNEL_ID)
            account_age = datetime.now(timezone.utc) - member.created_at
            print(f"Member: {member.name}, Account age: {account_age}, Created at: {member.created_at}")
            if account_age.total_seconds() <= (24 * 60 * 60):
                print(f"Adding role to {member.name}")
                await self.add_role(member, role, channel)

def setup(bot: commands.Bot) -> None:
    bot.add_cog(TadpoleLoungeCog(bot))