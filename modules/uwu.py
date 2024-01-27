# commands/uwu.py
import random

uwu_responses = [
    'Wibbit X3 *nuzzles*',
    'OwO',
    'Froggy hugs for you~',
    'Hai hai, Kero-chan desu~',
    'Froggy wisdom: always keep it kawaii, even in the rain!',
    'Froggy waifu for laifu!'
]

last_used_uwu = None

async def send_uwu_response(message):
    global last_used_uwu

    last_response = last_used_uwu
    available_responses = [response for response in uwu_responses if response != last_response]
    if not available_responses:
        available_responses = uwu_responses
    selected_response = random.choice(available_responses)
    last_used_uwu = selected_response
    await message.channel.send(selected_response)

async def on_message(message):
    # Trigger the response if a specific keyword is in the message
    if 'uwu' in message.content.lower():
        await send_uwu_response(message)