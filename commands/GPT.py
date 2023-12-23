# commands/GPT.py

import google.generativeai as genai
import openai
import asyncio
import os
from dotenv import load_dotenv

# Set your API keys from environment variables or a secure location
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize the Google AI client with your API key
genai.configure(api_key=GOOGLE_API_KEY)
# Initialize OpenAI
openai.api_key = OPENAI_API_KEY

async def ask_gpt(input_messages, retry_attempts=3, delay=1):
    for attempt in range(retry_attempts):
        try:
            combined_messages = " ".join(msg['content'] for msg in input_messages if msg['role'] == 'user')
            model = genai.GenerativeModel(
                model_name="gemini-pro",
                safety_settings=None  # Disabling safety settings
            )
            chat = model.start_chat()
            response = chat.send_message(combined_messages)
            return response.text
        except Exception as e:
            print(f"Error in ask_gpt with Google AI (attempt {attempt + 1}): {e}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(delay)
            else:
                # Fallback to OpenAI if Google AI fails
                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": combined_messages}]
                    )
                    return response.choices[0].message['content']
                except Exception as e:
                    print(f"Error in ask_gpt with OpenAI: {e}")
                    return "I'm sorry, I couldn't process that due to an error in both services."

    return "I'm sorry, I couldn't process that due to a server error with Google AI."
