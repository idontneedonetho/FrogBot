# modules.reactions.frog

async def on_message(message):
    if message.author.bot:
        return
    content_lower = message.content.lower()
    if content_lower == '🐸':
        await message.channel.send(":frog:")
        
def setup(client):
    client.add_listener(on_message, 'on_message')