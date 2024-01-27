import asyncio
import random

async def on_member_join(member):
    welcome_channel = member.guild.system_channel
    if welcome_channel:
        await asyncio.sleep(1)
        gif_links = ["https://cdn3.emoji.gg/emojis/1463-wave.gif"] * 49 + \
                    ["https://i.pinimg.com/originals/ab/bd/b6/abbdb6e66ec39dc9262abc617fbc2b02.gif"] * 49 + \
                    ["https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzhsN3Fnd2c1MG1hcmhwMG00czE5ZHZoZmZsa3k4N3hqcWJya2NwdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5xtDarIELDLO7lSFQJi/giphy.gif"]
        selected_gif = random.choice(gif_links)
        await welcome_channel.send(f"Hello {member.mention}!\n{selected_gif}")

def setup(bot):
    bot.event(on_member_join)