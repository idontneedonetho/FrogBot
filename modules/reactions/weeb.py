# models.reactions.weeb

async def on_message(message):
    if message.author.bot:
        return
    content_lower = message.content.lower()
    if content_lower == "weeb":
        await message.channel.send('https://media1.tenor.com/m/rM6sdvGLYCMAAAAC/bonk.gif')
        
def setup(client):
    client.add_listener(on_message, 'on_message')