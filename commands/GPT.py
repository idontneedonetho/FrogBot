# commands/GPT.py

import openai
from vertexai.preview.generative_models import GenerativeModel
import asyncio
import time

last_request_time = 0

def rate_limited_request():
    global last_request_time
    current_time = time.time()
    if current_time - last_request_time < 1:
        time.sleep(1 - (current_time - last_request_time))
    last_request_time = time.time()

async def ask_gpt(input_messages, retry_attempts=3, delay=1):
    frogbot_context = "I am FrogBot, your assistant for all questions related to FrogPilot and OpenPilot. I'll keep my responses under 2000 characters."
    
    assistant_id = "asst_koj1FbAIY2Y2eKxscCv2QcRV"  # Replace with your actual Assistant ID

    for attempt in range(retry_attempts):
        rate_limited_request()
        try:
            assistant = openai.Assistant.create(assistant_id=assistant_id)
            conversation = assistant.start_conversation()
            for msg in input_messages:
                if isinstance(msg, dict) and 'content' in msg and 'role' in msg:
                    conversation.send_message(msg['content'])
                elif isinstance(msg, str):
                    conversation.send_message(msg)
            response = conversation.get_latest_response()
            return response.message.content
        except Exception as e:
            print(f"Error in ask_gpt with OpenAI Assistant API: {e}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(delay)
                continue
            try:
                model = GenerativeModel(model_name="gemini-pro")
                chat = model.start_chat()
                gemini_input_messages = [frogbot_context] + input_messages
                response = chat.send_message("\n".join(gemini_input_messages))
                return response.text
            except Exception as e:
                print(f"Error in ask_gpt with Google AI: {e}")
    return "I'm sorry, I couldn't process that due to an error in both services."
