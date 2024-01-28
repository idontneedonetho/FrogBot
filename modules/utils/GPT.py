# commands/GPT.py

import os
import openai
import vertexai
from vertexai.preview.generative_models import GenerativeModel
import asyncio
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

async def ask_gpt(input_messages, retry_attempts=3, delay=1):
    gemini_context = "I am FrogBot, your assistant for all questions related to FrogPilot and OpenPilot. I'll keep my responses under 2000 characters."
    gpt_context = {"role": "system", "content": "I am FrogBot, your assistant for all questions related to FrogPilot and OpenPilot. I'll keep my responses under 2000 characters."}
    modified_input_messages = [gpt_context] + input_messages
    for attempt in range(retry_attempts):
        rate_limited_request()
        try:
            response = openai.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=modified_input_messages
            )
            response['choices'][0]['message']['content']
        except Exception as e:
            print(f"Error in ask_gpt with OpenAI API: {e}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(delay)
                continue
            try:
                model = GenerativeModel(model_name="Gemini-pro")
                chat = model.start_chat()
                gemini_input_messages = [gemini_context]
                for msg in input_messages:
                    if isinstance(msg, dict) and 'content' in msg:
                        gemini_input_messages.append(msg['content'])
                    elif isinstance(msg, str):
                        gemini_input_messages.append(msg)
                gemini_input_messages = [str(msg) for msg in gemini_input_messages]
                gemini_input_message_str = "\n".join(gemini_input_messages)
                response = chat.send_message(gemini_input_message_str)
                return response.text
            except Exception as e:
                print(f"Error in ask_gpt with Google AI: {e}")
    return "I'm sorry, I couldn't process that due to an error in both services."
