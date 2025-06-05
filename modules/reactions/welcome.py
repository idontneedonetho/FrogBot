# modules.reactions.welcome

from disnake.ext import commands
from core import config
import asyncio
import disnake
import logging
import random

class WelcomeCog(commands.Cog):
    SPECIAL_GIF_URL = "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzhsN3Fnd2c1MG1hcmhwMG00czE5ZHZoZmZsa3k4N3hqcWJya2NwdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5xtDarIELDLO7lSFQJi/giphy.gif"
    GIF_LINKS = [
        "https://cdn3.emoji.gg/emojis/1463-wave.gif",
        "https://i.pinimg.com/originals/ab/bd/b6/abbdb6e66ec39dc9262abc617fbc2b02.gif",
        SPECIAL_GIF_URL
    ]
    GIF_WEIGHTS = [49, 49, 1]
    DUNCE_ROLE_ID = 1372745158113759313
    MARSH_MENTOR_ROLE_ID = 1198482895342411846
    SPECIAL_GIF_ROLE_ID = 1333890145635799201
    NOTIFICATION_CHANNEL_ID = 1373016990838423684

    def __init__(self, bot):
        self.bot = bot

    def load_state(self):
        w_config = config.read()
        return w_config.get('non_successful_spawns', 0)

    def save_state(self, non_successful_spawns):
        config.update('non_successful_spawns', non_successful_spawns)

    async def send_welcome_message(self, channel, member, gif=None):
        try:
            await channel.send(f"Hello {member.mention}!")
            if gif:
                await channel.send(gif)
        except Exception as e:
            print(f"Failed to send welcome message or gif: {e}")
            await asyncio.sleep(10)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not member.pending:
            await self._handle_welcome(member)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.pending and not after.pending:
            await self._handle_welcome(after)
        dunce_role = self.get_guild_object(after.guild, "role", self.DUNCE_ROLE_ID)
        is_newly_dunce = dunce_role and dunce_role not in before.roles and dunce_role in after.roles
        if is_newly_dunce:
            await self._notify_dunce_role_assignment(after, dunce_role)

    async def _notify_dunce_role_assignment(self, member, dunce_role):
        notification_channel = self.get_guild_object(member.guild, "channel", self.NOTIFICATION_CHANNEL_ID)
        if not notification_channel:
            return
        mentor_role = self.get_guild_object(member.guild, "role", self.MARSH_MENTOR_ROLE_ID)
        mentor_mention = mentor_role.mention if mentor_role else "Marsh Mentors"
        message = (
            f"Hello {member.mention}, you've received the '{dunce_role.name}' role. To get full server access, "
            f"please revisit your onboarding answers and make them more realistic. The onboarding is at the "
            f"top of the channel list. {mentor_mention} are here to help if you have questions!"
        )
        try:
            await notification_channel.send(message)
            logging.info(f"Notified about {member.display_name} in #{notification_channel.name}")
        except disnake.Forbidden:
            logging.error(f"Missing permissions in #{notification_channel.name}")
        except Exception as e:
            logging.error(f"Notification failed: {e}")

    def get_guild_object(self, guild, object_type, object_id):
        if object_type == "role":
            obj = guild.get_role(object_id)
        elif object_type == "channel":
            obj = guild.get_channel(object_id)
        else:
            return None
        if not obj:
            logging.warning(f"{object_type.capitalize()} (ID: {object_id}) not found")
        return obj

    async def _handle_welcome(self, member):
        welcome_channel = member.guild.system_channel
        if not welcome_channel:
            return
        non_successful_spawns = self.load_state()
        spawn_probability = 0.05 + non_successful_spawns * 0.05
        if random.random() < spawn_probability:
            self.save_state(0)
            selected_gif = random.choices(self.GIF_LINKS, weights=self.GIF_WEIGHTS, k=1)[0]
            await self.send_welcome_message(welcome_channel, member, selected_gif)
            if selected_gif == self.SPECIAL_GIF_URL:
                special_role = self.get_guild_object(member.guild, "role", self.SPECIAL_GIF_ROLE_ID)
                if special_role:
                    await member.add_roles(special_role)
        else:
            non_successful_spawns += 1
            self.save_state(non_successful_spawns)
            await self.send_welcome_message(welcome_channel, member)

def setup(bot):
    bot.add_cog(WelcomeCog(bot))