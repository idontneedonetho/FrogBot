# modules.reactions.primary_mod

async def on_message(message):
    if message.author.bot:
        return
    content_lower = message.content.lower()
    if any(keyword in content_lower for keyword in ['primary mod']):
        await message.channel.send(':eyes:')
        
def setup(client):
    client.add_listener(on_message, 'on_message')