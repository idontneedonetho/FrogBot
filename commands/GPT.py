# commands/GPT.py

import vertexai
from vertexai.preview.generative_models import GenerativeModel
import openai
import asyncio
import os
import time
from dotenv import load_dotenv

load_dotenv()
vertexai.init(project=os.getenv('VERTEX_PROJECT_ID'))
openai.api_key = os.getenv('OPENAI_API_KEY')

last_request_time = 0

def rate_limited_request():
    global last_request_time
    current_time = time.time()
    if current_time - last_request_time < 1:
        time.sleep(1 - (current_time - last_request_time))
    last_request_time = time.time()

def count_prompt_tokens(prompt: str):
    model = GenerativeModel(model_name="gemini-pro")
    response = model.count_tokens(prompt)
    token_count = response.total_tokens
    return token_count

async def ask_gpt(input_messages, retry_attempts=3, delay=1):
    frogbot_context = "I am FrogBot, your assistant for all questions related to FrogPilot and OpenPilot. I'll keep my responses under 2000 characters."
    
    formatted_input_messages = [frogbot_context]
    for msg in input_messages:
        if isinstance(msg, dict) and 'content' in msg and 'role' in msg:
            formatted_input_messages.append(msg['content'])
        elif isinstance(msg, str):
            formatted_input_messages.append(msg)
    combined_messages = "\n".join(formatted_input_messages)

    for attempt in range(retry_attempts):
        rate_limited_request()
        try:
            model = GenerativeModel(model_name="gemini-pro")
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
