# commands/GPT.py

import os
import openai
import vertexai
from vertexai.preview.generative_models import GenerativeModel
import asyncio
from dotenv import load_dotenv
from modules.utils.search import handle_query, determine_information_type, estimate_confidence
from modules.utils.commons import send_long_message, fetch_reply_chain, fetch_message_from_link

load_dotenv()
vertexai.init(project=os.getenv('VERTEX_PROJECT_ID'))
openai.api_key = os.getenv('OPENAI_API_KEY')

async def process_message_with_llm(message, client):
    content = message.content.replace(client.user.mention, '').strip()
    if content:
        async with message.channel.typing():
            if content.startswith('https://discord.com/channels/'):
                linked_message = await fetch_message_from_link(client, content)
                if linked_message:
                    context = await fetch_reply_chain(linked_message)
                    combined_messages = [{'content': msg, 'role': 'user'} for msg in context]
                    combined_messages.append({'content': linked_message.content, 'role': 'user'})
                    response = await ask_gpt(combined_messages)
                    if not estimate_confidence(response):
                        print("Fetching additional information for uncertain queries.")
                        search_response, source_urls = await handle_query(linked_message.content)
                        response = await ask_gpt([search_response])
                        if source_urls:
                            response += "\n\n" + source_urls
                        response = response if response else "I'm sorry, I couldn't find information on that topic."
                else:
                    response = "I couldn't fetch the message from the link."
            else:
                context = await fetch_reply_chain(message)
                combined_messages = [{'content': msg, 'role': 'user'} for msg in context]
                combined_messages.append({'content': content, 'role': 'user'})
                response = await ask_gpt(combined_messages)
                if not estimate_confidence(response):
                    print("Fetching additional information for uncertain queries.")
                    search_response, source_urls = await handle_query(content)
                    response = await ask_gpt([search_response])
                    if source_urls:
                        response += "\n\n" + source_urls
                    response = response if response else "I'm sorry, I couldn't find information on that topic."
            response = response.replace(client.user.name + ":", "").strip()
            await send_long_message(message, response)

async def ask_gpt(input_messages, retry_attempts=3, delay=1, bit_flip=1):
    gemini_context = "I am FrogBot, your assistant for all questions related to FrogPilot and OpenPilot. I'll keep my responses under 2000 characters. I am powered by Gemini-Pro"
    gpt_context = {"role": "system", "content": "I am FrogBot, your assistant for all questions related to FrogPilot and OpenPilot. I'll keep my responses under 2000 characters. I am powered by GPT-4 Turbo."}
    modified_input_messages = [gpt_context] + input_messages
    for attempt in range(retry_attempts):
        try:
            if bit_flip:
                response = openai.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=modified_input_messages
                )
                response_message = response.choices[0].message.content
            else:
                model = GenerativeModel(model_name="gemini-pro")
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
                response_message = response.text
            return response_message
        except Exception as e:
            print(f"Error in ask_gpt with OpenAI API: {e}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(delay)
                continue
            try:
                if bit_flip:
                    model = GenerativeModel(model_name="gemini-pro")
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
                    response_message = response.text
                else:
                    response = openai.chat.completions.create(
                        model="gpt-4-turbo-preview",
                        messages=modified_input_messages
                    )
                    response_message = response.choices[0].message.content
                return response_message
            except Exception as e:
                print(f"Error in ask_gpt with Google AI: {e}")
    return "I'm sorry, I couldn't process that due to an error in both services."