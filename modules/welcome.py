# commands/welcome.py

# This module doesn't use the commands dictionary since it's for an event, not a command
cmd = {}

async def on_member_join(member):
    welcome_channel = member.guild.system_channel
    if welcome_channel:
        await welcome_channel.send(f"https://cdn3.emoji.gg/emojis/1463-wave.gif")
