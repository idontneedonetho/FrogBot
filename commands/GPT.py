import google.generativeai as genai
import openai
from PIL import Image
import re
import asyncio
import aiohttp
import tempfile
import os
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

genai.configure(api_key=GOOGLE_API_KEY)
openai.api_key = OPENAI_API_KEY

safety_settings = {
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE"
}

async def download_image(image_url):
    print(f"Downloading image from URL: {image_url}")
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status == 200:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                    temp_file.write(await response.read())
                    print(f"Image downloaded and saved to temporary file: {temp_file.name}")
                    return temp_file.name
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
    try:
        if is_image:
            image_url = input_messages[0]['content']
            if not re.search(r'\.(jpeg|jpg|png)', image_url.lower()):
                print("Invalid image format detected.")
                return "Invalid image format. Only JPEG and PNG are supported."

            temp_file_path = await download_image(image_url)
            if temp_file_path is None:
                return "Failed to download the image."

            response_text = await process_image_with_google_api(temp_file_path)
            os.remove(temp_file_path)
            print("Temporary file deleted after processing.")
            return response_text
        else:
            combined_messages = " ".join(msg['content'] for msg in input_messages if msg['role'] == 'user')
            model = genai.GenerativeModel(model_name="gemini-pro", safety_settings=safety_settings)
            chat = model.start_chat()
            print(f"Sending text to Google AI: {combined_messages}")
            response = chat.send_message(combined_messages)
            return response.text

    except Exception as e:
        print(f"Error in ask_gpt with Google AI: {e}")
        if retry_attempts > 0:
            await asyncio.sleep(delay)
            return await ask_gpt(input_messages, is_image, retry_attempts - 1, delay)
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
