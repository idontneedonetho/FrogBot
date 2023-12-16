# commands/GPT.py

import openai
import os
import asyncio
from discord.ext import commands

openai.api_key = os.getenv("OPENAI_API_KEY")

async def ask_gpt(input_messages, retry_attempts=3, delay=1):
    for attempt in range(retry_attempts):
        try:
            messages_payload = input_messages
            if not input_messages:
                messages_payload = [{"role": "system", "content": "You are a helpful assistant."},
                                    {"role": "user", "content": " "}]

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages_payload
            )
            return response.choices[0].message['content']
        except Exception as e:
            print(f"Error in ask_gpt (attempt {attempt + 1}): {e}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(delay)

    return "I'm sorry, I couldn't process that due to a server error."
