import asyncio

async def on_member_join(member):
    welcome_channel = member.guild.system_channel
    if welcome_channel:
        await asyncio.sleep(0.5)
        await welcome_channel.send(f"Hello {member.mention}! https://cdn3.emoji.gg/emojis/1463-wave.gif")

def setup(bot):
    bot.event(on_member_join)