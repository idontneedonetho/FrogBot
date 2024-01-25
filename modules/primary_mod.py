# commands/primary_mod_reaction.py

cmd = {}  # No specific commands for this module

async def on_message(message):
    content_lower = message.content.lower()
    if any(keyword in content_lower for keyword in ['primary mod']):
        await message.channel.send(':eyes:')