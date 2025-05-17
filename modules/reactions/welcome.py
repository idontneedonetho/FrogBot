# modules.reactions.welcome

from disnake.ext import commands
import logging
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

    async def send_tadpole_welcome(self, channel, member):
        try:
            await channel.send(f"Welcome aboard, {member.mention}! You've successfully completed onboarding and received the Tadpole role!")
        except Exception as e:
            logging.error(f"Failed to send Tadpole welcome message to {member.display_name} in {channel.name}: {e}")

    async def send_random_gif(self, channel, member):
        try:
            selected_gif = random.choices(self.GIF_LINKS, weights=self.GIF_WEIGHTS, k=1)[0]
            await channel.send(selected_gif)
            if selected_gif == "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzhsN3Fnd2c1MG1hcmhwMG00czE5ZHZoZmZsa3k4N3hqcWJya2NwdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5xtDarIELDLO7lSFQJi/giphy.gif":
                special_role_id_str = self.bot.config_data.get('SPECIAL_GIF_ROLE_ID', '0') if hasattr(self.bot, 'config_data') else '0'
                special_role_id = int(special_role_id_str) if special_role_id_str.isdigit() else 0
                if special_role_id != 0:
                    role = member.guild.get_role(special_role_id)
                    if role:
                        await member.add_roles(role, reason="Special welcome GIF interaction")
                        logging.info(f"Assigned special role {role.name} to {member.display_name} for welcome GIF.")
                    else:
                        logging.warning(f"Special GIF role ID {special_role_id} not found in guild {member.guild.name}.")
                elif hasattr(self.bot, 'config_data') and 'SPECIAL_GIF_ROLE_ID' in self.bot.config_data: # only log if it was expected
                    logging.warning(f"SPECIAL_GIF_ROLE_ID is configured but is 0 or invalid, not assigning role for GIF.")
        except Exception as e:
            logging.error(f"Failed to send welcome GIF to {member.display_name} in {channel.name}: {e}")

def setup(bot):
    bot.add_cog(WelcomeCog(bot))
    logging.info("WelcomeCog (modified for Tadpole welcome) has been loaded.")