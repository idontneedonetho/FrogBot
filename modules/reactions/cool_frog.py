# modules.reactions.cool_frog

async def on_message(message):
    if message.author.bot:
        return
    content_lower = message.content.lower()
    if ':coolfrog:' in content_lower:
        await message.channel.send('<:coolfrog:1168605051779031060>')

def setup(client):
    client.add_listener(on_message, 'on_message')