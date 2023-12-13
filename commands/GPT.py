# commands/GPT.py

import openai
import os
import asyncio
from discord.ext import commands
print('GPT.py loaded')

openai.api_key = os.getenv("OPENAI_API_KEY")

async def ask_gpt(question):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                      {"role": "user", "content": question}]
        )
        return response.choices[0].message['content']
    except Exception as e:
        print(f"Error in ask_gpt: {e}")
        return "I'm sorry, I couldn't process that."