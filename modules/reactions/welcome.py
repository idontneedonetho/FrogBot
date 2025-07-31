# modules.reactions.welcome

from disnake.ext import commands
from core import config
import logging
import disnake
import random
import time

class WelcomeCog(commands.Cog):
    SPECIAL_GIF_URL = "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzhsN3Fnd2c1MG1hcmhwMG00czE5ZHZoZmZsa3k4N3hqcWJya2NwdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5xtDarIELDLO7lSFQJi/giphy.gif"
    NORMAL_GIFS = [
        "https://cdn3.emoji.gg/emojis/1463-wave.gif",
        "https://i.pinimg.com/originals/ab/bd/b6/abbdb6e66ec39dc9262abc617fbc2b02.gif"
    ]
    BASE_SPECIAL_GIF_CHANCE = 0.0001
    CHANCE_INCREMENT = 0.0001
    DUNCE_ROLE_ID = 1372745158113759313
    SPECIAL_GIF_ROLE_ID = 1333890145635799201
    NOTIFICATION_CHANNEL_ID = 1373016990838423684
    dunce_role_timestamps = {}

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: disnake.Member):
        if not member.pending:
            await self._handle_welcome(member)

    @commands.Cog.listener()
    async def on_member_update(self, before: disnake.Member, after: disnake.Member):
        if before.pending and not after.pending:
            await self._handle_welcome(after)
        dunce_role = self.get_guild_object(after.guild, "role", self.DUNCE_ROLE_ID)
        if dunce_role:
            had_dunce_before = dunce_role in before.roles
            has_dunce_now = dunce_role in after.roles
            if not had_dunce_before and has_dunce_now:
                self.dunce_role_timestamps[after.id] = time.time()
            elif has_dunce_now:
                assigned_time = self.dunce_role_timestamps.get(after.id)
                if assigned_time and (time.time() - assigned_time) >= 3600:
                    await self._notify_dunce_role_assignment(after, dunce_role)
                    del self.dunce_role_timestamps[after.id]

    async def _handle_welcome(self, member: disnake.Member):
        welcome_channel = member.guild.system_channel
        if not welcome_channel:
            return
        non_successful_spawns = self.load_state()
        special_chance = self.BASE_SPECIAL_GIF_CHANCE + (non_successful_spawns * self.CHANCE_INCREMENT)
        if random.random() < special_chance:
            selected_gif = self.SPECIAL_GIF_URL
            self.save_state(0)
            special_role = self.get_guild_object(member.guild, "role", self.SPECIAL_GIF_ROLE_ID)
            if special_role:
                await member.add_roles(special_role)
        else:
            selected_gif = random.choice(self.NORMAL_GIFS)
            self.save_state(non_successful_spawns + 1)
        await self.send_welcome_message(welcome_channel, member, selected_gif)

    async def _notify_dunce_role_assignment(self, member: disnake.Member, dunce_role: disnake.Role):
        notification_channel = self.get_guild_object(member.guild, "channel", self.NOTIFICATION_CHANNEL_ID)
        if not notification_channel:
            return
        message = (
            f"Hello {member.mention}!\n\n"
            "You've been given the \"Dunce\" role for now. No worries, it just means your onboarding answers could use a bit more thought!\n\n"
            "To unlock full access to the server, please revisit your onboarding at the top of the channel list under \"Channels & Roles\".\n\n"
            "If you're unsure what to change or need a hand, feel free to ping `@Marsh Mentors`!"
        )
        await notification_channel.send(message)

    async def send_welcome_message(self, channel: disnake.TextChannel, member: disnake.Member, gif_url: str):
        await channel.send(f"Hello {member.mention}!")
        await channel.send(gif_url)

    def get_guild_object(self, guild: disnake.Guild, object_type: str, object_id: int):
        obj = None
        if object_type == "role":
            obj = guild.get_role(object_id)
        elif object_type == "channel":
            obj = guild.get_channel(object_id)
        if not obj:
            logging.warning(f"{object_type.capitalize()} with ID {object_id} not found.")
        return obj

    def load_state(self) -> int:
        w_config = config.read()
        return w_config.get('non_successful_spawns', 0)

    def save_state(self, non_successful_spawns: int):
        config.update('non_successful_spawns', non_successful_spawns)

def setup(bot: commands.Bot):
    bot.add_cog(WelcomeCog(bot))