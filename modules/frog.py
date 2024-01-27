# commands/frog_reaction.py

async def on_message(message):
    content_lower = message.content.lower()
    if content_lower == '🐸':
        await message.channel.send(":frog:")