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
    frogbot_context = "You are FrogBot, a Discord bot assistant for all questions related to FrogPilot and OpenPilot. You are located in the FrogPilot discord and you answer to @FrogsGoMoo and @idnot . You'll keep your responses under 2000 characters. You will also provide snarky responses on occasion. Don't be kinky you weirdo."

    for attempt in range(retry_attempts):
        rate_limited_request()
        try:
            thread = client.beta.threads.create()
            assistant = openai.beta.assistants.create(
                name="FrogBot",
                instructions="You are FrogBot, a Discord bot assistant for all questions related to FrogPilot and OpenPilot. You are located in the FrogPilot discord and you answer to @FrogsGoMoo and @idontneedonetho . You'll keep your responses under 2000 characters. You will also provide snarky responses on occasion. You can reference FrogPilot-txt.zip for any FrogPilot questions. Don't be kinky you weirdo.",
                model="gpt-4-1106-preview"
            )
            for msg in input_messages:
                if isinstance(msg, dict) and 'content' in msg and 'role' in msg:
                    message = client.beta.threads.messages.create(
                        thread_id=thread.id,
                        role="user",
                        content=msg['content']
                    )
                elif isinstance(msg, str):
                    message = client.beta.threads.messages.create(
                        thread_id=thread.id,
                        role="user",
                        content=msg
                    )
            run = client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=assistant.id,
            )

            while True:
                run_status = client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )

                if run_status['status'] == "completed":
                    break
        
                time.sleep(1)
                
            messages = client.beta.threads.messages.list(
                thread_id=thread.id
            )

            last_assistant_response = None
            for msg in reversed(messages["data"]):
                if msg["role"] == "assistant":
                    last_assistant_response = msg["content"][0]["text"]["value"]
                    break

                return last_assistant_response
            
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
