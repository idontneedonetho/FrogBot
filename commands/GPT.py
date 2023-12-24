import google.generativeai as genai
import openai
from PIL import Image
from io import BytesIO
import asyncio
import aiohttp
import os
from dotenv import load_dotenv

# Load API keys from environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Configure APIs
genai.configure(api_key=GOOGLE_API_KEY)
openai.api_key = OPENAI_API_KEY

# Asynchronous function to download an image
async def download_image(image_url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status == 200:
                return await response.read()
            return None

# Function to process requests to GPT models
async def ask_gpt(input_messages, is_image=False, retry_attempts=3, delay=1):
    try:
        if is_image:
            image_url = input_messages[0]['content']
            if not image_url.lower().endswith(('.jpeg', '.jpg', '.png')):
                return "Invalid image format. Only JPEG and PNG are supported."

            image_data = await download_image(image_url)
            if image_data is None:
                return "Failed to download the image."

            image = Image.open(BytesIO(image_data))
            model = genai.GenerativeModel(model_name="gemini-pro-vision")
            response = model.generate_content([image])
            return response.text

        else:
            combined_messages = " ".join(msg['content'] for msg in input_messages if msg['role'] == 'user')
            for attempt in range(retry_attempts):
                try:
                    model = genai.GenerativeModel(model_name="gemini-pro", safety_settings=None)
                    chat = model.start_chat()
                    response = chat.send_message(combined_messages)
                    return response.text
                except Exception as e:
                    if attempt >= retry_attempts - 1:
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
                    await asyncio.sleep(delay)
    except Exception as e:
        print(f"Error in ask_gpt: {e}")

    return "I'm sorry, I couldn't process that due to a server error with Google AI."
