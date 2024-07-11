# modules.reactions.radar_bat

from disnake.ext import commands

class RadarBatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        content_lower = message.content.lower()
        if 'radar' in content_lower:
            await message.channel.send(':bat:')

def setup(bot):
    bot.add_cog(RadarBatCog(bot))
