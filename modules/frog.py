# commands/frog_reaction.py

cmd = {}  # No specific commands for this module

async def on_message(message):
    content_lower = message.content.lower()
    if content_lower == '🐸':
        await message.channel.send(":frog:")