# modules.reactions.welcome

from disnake.ext import commands
from core import config
import asyncio
import random

class WelcomeCog(commands.Cog):
    GIF_LINKS = [
        "https://cdn3.emoji.gg/emojis/1463-wave.gif",
        "https://i.pinimg.com/originals/ab/bd/b6/abbdb6e66ec39dc9262abc617fbc2b02.gif",
        "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzhsN3Fnd2c1MG1hcmhwMG00czE5ZHZoZmZsa3k4N3hqcWJya2NwdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5xtDarIELDLO7lSFQJi/giphy.gif"
    ]
    GIF_WEIGHTS = [49, 49, 1]

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
        welcome_channel = member.guild.system_channel
        if welcome_channel:
            await asyncio.sleep(5)
            non_successful_spawns = self.load_state()
            spawn_probability = 0.05 + non_successful_spawns * 0.05
            if random.random() < spawn_probability:
                selected_gif = random.choices(self.GIF_LINKS, weights=self.GIF_WEIGHTS, k=1)[0]
                await self.send_welcome_message(welcome_channel, member, selected_gif)
                if selected_gif == "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzhsN3Fnd2c1MG1hcmhwMG00czE5ZHZoZmZsa3k4N3hqcWJya2NwdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5xtDarIELDLO7lSFQJi/giphy.gif":
                    role = member.guild.get_role(1333890145635799201)
                    if role:
                        await member.add_roles(role)
                    else:
                        print(f"Role with ID 1333890145635799201 not found.")
            else:
                non_successful_spawns += 1
                self.save_state(non_successful_spawns)
                await self.send_welcome_message(welcome_channel, member)

def setup(bot):
    bot.add_cog(WelcomeCog(bot))