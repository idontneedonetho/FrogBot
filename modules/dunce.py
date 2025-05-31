# modules.dunce

from disnake.ext import commands
import disnake
import logging

DUNCE_ROLE_ID = 1372745158113759313
MARSH_MENTOR_ROLE_ID = 1198482895342411846

class DunceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: disnake.Member, after: disnake.Member):
        dunce_role = after.guild.get_role(DUNCE_ROLE_ID)
        if not dunce_role:
            logging.error(f"Dunce role (ID: {DUNCE_ROLE_ID}) not found")
            return
        if dunce_role in before.roles or dunce_role not in after.roles:
            return
        mentor_role = after.guild.get_role(MARSH_MENTOR_ROLE_ID)
        mentor_mention = mentor_role.mention if mentor_role else "Marsh Mentors"
        if not mentor_role:
            logging.warning(f"Marsh Mentor role (ID: {MARSH_MENTOR_ROLE_ID}) not found")
        notification_channel = self.find_notification_channel(after.guild)
        if not notification_channel:
            logging.warning(f"No suitable channel found in {after.guild.name}")
            return
        try:
            await notification_channel.send(
                f"Hey {mentor_mention}! {after.mention} has just been assigned the "
                f"{dunce_role.name} role. Please welcome them!"
            )
            logging.info(f"Notified about {after.display_name} in #{notification_channel.name}")
        except disnake.Forbidden:
            logging.error(f"Missing permissions in #{notification_channel.name}")
        except Exception as e:
            logging.error(f"Notification failed: {e}")

    def find_notification_channel(self, guild):
        lost_channel = guild.get_channel(1373016990838423684)
        if lost_channel and lost_channel.permissions_for(guild.me).send_messages:
            return lost_channel
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            return guild.system_channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                return channel
        return None

def setup(bot):
    bot.add_cog(DunceCog(bot))
    logging.info("DunceCog has been loaded.") 