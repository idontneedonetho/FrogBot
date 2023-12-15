# commands/GPT.py

import openai
import os
import asyncio
from discord.ext import commands

print('GPT.py loaded')

openai.api_key = os.getenv("OPENAI_API_KEY")

async def ask_gpt(input_messages, retry_attempts=3, delay=1):
    for attempt in range(retry_attempts):
        try:
            conversation = ""
            for message in input_messages:
                role = message.get("role", "user")
                content = message.get("content", "")
                conversation += f"{role}: {content}\n"

            response = openai.Completion.create(
                model="gpt-3.5-turbo",
                prompt=conversation,
                max_tokens=4096
            )
            return response.choices[0].text.strip()
        except Exception as e:
            print(f"Error in ask_gpt (attempt {attempt + 1}): {e}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(delay)

    return "I'm sorry, I couldn't process that due to a server error."
