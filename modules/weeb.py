# commands/weeb_reaction.py

cmd = {}  # No specific commands for this module

async def on_message(message):
    content_lower = message.content.lower()
    if content_lower == "weeb":
        await message.channel.send('https://media1.tenor.com/m/rM6sdvGLYCMAAAAC/bonk.gif')