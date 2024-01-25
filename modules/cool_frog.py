# commands/cool_frog_reaction.py

cmd = {}  # No specific commands for this module

async def on_message(message):
    content_lower = message.content.lower()
    if ':coolfrog:' in content_lower:
        await message.channel.send('<:coolfrog:1168605051779031060>')