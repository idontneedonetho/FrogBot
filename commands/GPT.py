# commands/GPT.py

import google.generativeai as genai
import openai
import PIL.Image
import http.client
import typing
import re
import urllib.request
import asyncio
import io
import os
from dotenv import load_dotenv
from vertexai.preview.generative_models import GenerativeModel, Image

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

genai.configure(api_key=GOOGLE_API_KEY)
openai.api_key = OPENAI_API_KEY

def load_image_from_url(image_url: str) -> PIL.Image.Image:
    with urllib.request.urlopen(image_url) as response:
        image_data = response.read()
    image = PIL.Image.open(io.BytesIO(image_data))
    return image

async def ask_gpt(input_messages, is_image=False, retry_attempts=3, delay=1):
    try:
        if is_image:
            # Validate and download the image
            image_url = input_messages[0]['content']
            if not image_url.endswith(('.jpeg', '.jpg', '.png')):
                return "Invalid image format. Only JPEG and PNG are supported."
            # Download the image
            image = load_image_from_url(image_url)
            # Check if the image is successfully downloaded
            if image is None:
                return "Failed to download the image."
            # Process the image using gemini-pro-vision
            model = genai.GenerativeModel(model_name="gemini-pro-vision")
            response = model.generate_content([image])
            return response.text
        else:
            combined_messages = " ".join(msg['content'] for msg in input_messages if msg['role'] == 'user')
            for attempt in range(retry_attempts):
                try:
                    model = genai.GenerativeModel(
                        model_name="gemini-pro",
                        safety_settings=None
                    )
                    chat = model.start_chat()
                    response = chat.send_message(combined_messages)
                    return response.text
                except Exception as e:
                    if attempt >= retry_attempts - 1:
                        return "Failed to process text after several attempts."
                    await asyncio.sleep(delay)
    except Exception as e:
            print(f"Error in ask_gpt with Google AI (attempt {attempt + 1}): {e}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(delay)
            else:
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
    return "I'm sorry, I couldn't process that due to a server error with Google AI."
