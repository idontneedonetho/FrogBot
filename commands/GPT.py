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
import io
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

genai.configure(api_key=GOOGLE_API_KEY)
openai.api_key = OPENAI_API_KEY

API_PROMPT = ("You're a helpful Discord bot, designed to provide useful and concise "
              "answers. Remember to limit your responses to 2000 characters or less, "
              "focusing on delivering clear and relevant information in a friendly and "
              "engaging manner.")

async def download_image(image_url):
    print(f"Downloading image from URL: {image_url}")
    uid = str(uuid.uuid4())
    images_dir = Path('./images')
    images_dir.mkdir(exist_ok=True)
    file_path = images_dir / f"{uid}.jpg"
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status == 200:
                image_data = await response.read()
                image = Image.open(io.BytesIO(image_data))
                image = compress_image(image, max_size=4*1024*1024)
                image.save(file_path, quality=85, optimize=True)
                print(f"Image downloaded and compressed as: {file_path}")
                return uid
            else:
                print(f"Failed to download image. HTTP status: {response.status}")
                return None

def compress_image(image, max_size):
    img_byte_arr = io.BytesIO()
    quality = 95
    while True:
        img_byte_arr.seek(0)
        image.save(img_byte_arr, format='JPEG', quality=quality)
        if img_byte_arr.tell() <= max_size or quality <= 10:
            break
        quality -= 5
    img_byte_arr.seek(0)
    return Image.open(img_byte_arr)

async def process_image_with_google_api(temp_file_path):
    def process_image():
        print(f"Processing image with Google API: {temp_file_path}")
        image = Image.open(temp_file_path)
        model = genai.GenerativeModel(model_name="gemini-pro-vision")
        return model.generate_content([image]).text
    return await asyncio.to_thread(process_image)

async def ask_gpt(input_messages, is_image=False, context_uids=[], retry_attempts=3, delay=1):
    combined_messages = API_PROMPT + " " + " ".join(msg['content'] for msg in input_messages if msg['role'] == 'user')
    for uid in context_uids:
        image_path = Path('./images') / f'{uid}.jpg'
        if image_path.exists():
            response_text = await process_image_with_google_api(image_path)
            combined_messages += " " + response_text
        else:
            print(f"Image with UID {uid} not found in context.")
    for attempt in range(retry_attempts):
        try:
            if is_image:
                uid = None
                for msg in input_messages:
                    uid_match = re.search(r'> Image UID: (\S+)', msg['content'])
                    if uid_match:
                        uid = uid_match.group(1)
                        break
                if uid:
                    image_path = Path('./images') / f'{uid}.jpg'
                    if not image_path.exists():
                        print(f"Image not found at path: {image_path}")
                        return "Image not found."
                    response_text = await process_image_with_google_api(image_path)
                    print("Image processing completed.")
                    return response_text + f"\n> Image UID: {uid}"
                else:
                    print("No valid UID found in the message.")
                    return "No valid UID found."
            model = genai.GenerativeModel(model_name="gemini-pro")
            chat = model.start_chat()
            print(f"Sending text to Google AI: {combined_messages}")
            response = chat.send_message(combined_messages)
            return response.text
        except Exception as e:
            print(f"Error in ask_gpt with Google AI: {e}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(delay)
                continue
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
