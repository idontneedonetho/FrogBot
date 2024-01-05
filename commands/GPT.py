# commands/GPT.py

import google.generativeai as genai
import openai
import os
import time
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
openai.api_key = os.getenv('OPENAI_API_KEY')

last_request_time = 0
safety_settings = {
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE"
}

def rate_limited_request():
    global last_request_time
    current_time = time.time()
    if current_time - last_request_time < 1:
        time.sleep(1 - (current_time - last_request_time))
    last_request_time = time.time()

async def ask_gpt(input_messages, retry_attempts=3, delay=1):
    formatted_input_messages = []
    for msg in input_messages:
        if isinstance(msg, dict) and 'content' in msg and 'role' in msg:
            formatted_input_messages.append(msg)
        elif isinstance(msg, str):
            formatted_input_messages.append({"role": "user", "content": msg})
    combined_messages = "\n".join(f"{msg['content']}" for msg in formatted_input_messages if msg['role'] == 'user')
    for attempt in range(retry_attempts):
        rate_limited_request()
        try:
            model = genai.GenerativeModel(model_name="gemini-pro", safety_settings=safety_settings)
            chat = model.start_chat()
            response = chat.send_message(combined_messages)
            return response.text
        except Exception as e:
            print(f"Error in ask_gpt with Google AI: {e}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(delay)
                continue
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": combined_messages}]
                )
                return response.choices[0].message['content']
            except Exception as e:
                print(f"Error in ask_gpt with OpenAI: {e}")
    return "I'm sorry, I couldn't process that due to an error in both services."
