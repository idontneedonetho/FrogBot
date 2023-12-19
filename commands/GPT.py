# commands/GPT.py

import google.generativeai as genai
import asyncio
import os
from dotenv import load_dotenv

# Set your API key from an environment variable or a secure location
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Initialize the Google AI client with your API key
genai.configure(api_key=GOOGLE_API_KEY)

async def ask_gpt(input_messages, retry_attempts=3, delay=1):
    for attempt in range(retry_attempts):
        try:
            # Assuming you can start a chat and send messages in a similar way to OpenAI
            combined_messages = " ".join(msg['content'] for msg in input_messages if msg['role'] == 'user')
            model = genai.GenerativeModel("gemini-pro")
            chat = model.start_chat()
            response = chat.send_message(combined_messages)
            return response.text
        except Exception as e:
            print(f"Error in ask_gpt (attempt {attempt + 1}): {e}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(delay)

    return "I'm sorry, I couldn't process that due to a server error."