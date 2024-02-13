# modules.reactions.owo

import random

owo_responses = [
    'o3o',
    'UwU',
    'Hoppy-chan kawaii desu~',
    'Ribbit-senpai noticed you!',
    'Froggy power, activate! Transform into maximum kawaii mode!',
    'Wibbit-senpai, notice my kawaii vibes!'
]

last_used_owo = None

async def send_owo_response(message):
    global last_used_owo

    last_response = last_used_owo
    available_responses = [response for response in owo_responses if response != last_response]
    if not available_responses:
        available_responses = owo_responses
    selected_response = random.choice(available_responses)
    last_used_owo = selected_response
    await message.channel.send(selected_response)

async def on_message(message):
    if message.author.bot:
        return
    if 'owo' in message.content.lower():
        await send_owo_response(message)

def setup(client):
    client.add_listener(on_message, 'on_message')