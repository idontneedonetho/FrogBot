# commands/GPT.py

import google.generativeai as genai
import openai
import re
from PIL import Image
from pathlib import Path
import asyncio
import aiohttp
import uuid
import os
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

genai.configure(api_key=GOOGLE_API_KEY)
openai.api_key = OPENAI_API_KEY

# safety_settings = {
#     "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
#     "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
#     "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
#     "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE"
# }

async def download_image(image_url):
    print(f"Downloading image from URL: {image_url}")
    uid = str(uuid.uuid4())
    images_dir = Path('./images')
    images_dir.mkdir(exist_ok=True)
    file_path = images_dir / f"{uid}.jpg"

    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status == 200:
                file_path.write_bytes(await response.read())
                print(f"Image downloaded and saved as: {file_path}")
                return uid
            else:
                print(f"Failed to download image. HTTP status: {response.status}")
                return None

async def process_image_with_google_api(temp_file_path):
    print(f"Processing image with Google API: {temp_file_path}")
    image = Image.open(temp_file_path)
    model = genai.GenerativeModel(model_name="gemini-pro-vision", safety_settings=safety_settings)
    response = model.generate_content([image])
    return response.text

async def ask_gpt(input_messages, is_image=False, retry_attempts=3, delay=1):
    for attempt in range(retry_attempts):
        try:
            if is_image:
                uid = None
                for msg in input_messages:
                    uid_match = re.search(r'> Image UID: (\S+)', msg['content'])
                    if uid_match:
                        uid = uid_match.group(1)
                        break

                if uid_found:
                    image_path = Path('./images') / f'{uid}.jpg'
                    if not image_path.exists():
                        print(f"Image not found at path: {image_path}")
                        return "Image not found."
                    response_text = await process_image_with_google_api(Path('./images') / f'{uid}.jpg')
                    return response_text + f"\n> Image UID: {uid}"
                else:
                    return "No valid UID found."
            else:
                combined_messages = " ".join(msg['content'] for msg in input_messages if msg['role'] == 'user')
                model = genai.GenerativeModel(model_name="gemini-pro", safety_settings=safety_settings)
                chat = model.start_chat()
                print(f"Sending text to Google AI: {combined_messages}")
                response = chat.send_message(combined_messages)
                return response.text

        except Exception as e:
            print(f"Error in ask_gpt with Google AI: {e}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(delay)
            else:
                try:
                    print("Fallback to OpenAI due to Google AI failure.")
                    response = openai.ChatCompletion.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": combined_messages}]
                    )
                    return response.choices[0].message['content']
                except Exception as e:
                    print(f"Error in ask_gpt with OpenAI: {e}")
    return "I'm sorry, I couldn't process that due to an error in both services."
