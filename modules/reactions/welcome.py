# modules.reactions.welcome

from disnake.ext import commands
from core import config
import asyncio
import disnake
import logging
import random

class WelcomeCog(commands.Cog):
    GIF_LINKS = [
        "https://cdn3.emoji.gg/emojis/1463-wave.gif",
        "https://i.pinimg.com/originals/ab/bd/b6/abbdb6e66ec39dc9262abc617fbc2b02.gif",
        "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzhsN3Fnd2c1MG1hcmhwMG00czE5ZHZoZmZsa3k4N3hqcWJya2NwdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5xtDarIELDLO7lSFQJi/giphy.gif"
    ]
    GIF_WEIGHTS = [49, 49, 1]
    DUNCE_ROLE_ID = 1372745158113759313
    MARSH_MENTOR_ROLE_ID = 1198482895342411846
    SPECIAL_GIF_ROLE_ID = 1333890145635799201

    def __init__(self, bot):
        self.bot = bot
        self.pending_members = set()

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
        if member.pending:
            self.pending_members.add(member.id)
        else:
            await self._handle_welcome(member)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.pending and not after.pending and after.id in self.pending_members:
            self.pending_members.remove(after.id)
            await self._handle_welcome(after)
        dunce_role = after.guild.get_role(self.DUNCE_ROLE_ID)
        if not dunce_role:
            logging.error(f"Dunce role (ID: {self.DUNCE_ROLE_ID}) not found")
            return
        if dunce_role in before.roles or dunce_role not in after.roles:
            return
        mentor_role = after.guild.get_role(self.MARSH_MENTOR_ROLE_ID)
        mentor_mention = mentor_role.mention if mentor_role else "Marsh Mentors"
        if not mentor_role:
            logging.warning(f"Marsh Mentor role (ID: {self.MARSH_MENTOR_ROLE_ID}) not found")
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

    async def _handle_welcome(self, member):
        welcome_channel = member.guild.system_channel
        if welcome_channel:
            non_successful_spawns = self.load_state()
            spawn_probability = 0.05 + non_successful_spawns * 0.05
            if random.random() < spawn_probability:
                selected_gif = random.choices(self.GIF_LINKS, weights=self.GIF_WEIGHTS, k=1)[0]
                await self.send_welcome_message(welcome_channel, member, selected_gif)
                if selected_gif == "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzhsN3Fnd2c1MG1hcmhwMG00czE5ZHZoZmZsa3k4N3hqcWJya2NwdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5xtDarIELDLO7lSFQJi/giphy.gif":
                    role = member.guild.get_role(self.SPECIAL_GIF_ROLE_ID)
                    await member.add_roles(role)
            else:
                non_successful_spawns += 1
                self.save_state(non_successful_spawns)
                await self.send_welcome_message(welcome_channel, member)

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
    bot.add_cog(WelcomeCog(bot))