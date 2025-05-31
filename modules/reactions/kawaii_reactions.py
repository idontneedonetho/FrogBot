# modules.reactions.kawaii_reactions

import google.generativeai as genai
from disnake.ext import commands
from core import config
import random

class KawaiiReactionsCog(commands.Cog):
    __slots__ = ('bot', 'fallback_responses', 'last_used', 'gemini_model')
    
    SYSTEM_PROMPTS = {
        'uwu': "You are a shy, sweet anime-speaking frog. Generate ONE short kawaii response directly addressing the user's message with clear and relevant content using uwu-style speech patterns. Include frog terms, emoticons, and lots of '~' characters. Be extremely cute, gentle, and ensure your response is not vague.",
        'owo': "You are an energetic, excited anime-speaking frog. Generate ONE short kawaii response directly addressing the user's message with clear and relevant content using owo-style speech patterns. Include frog terms, emoticons, and lots of '*action*' text. Be bouncy, enthusiastic, and ensure your response is directly connected to the user's message."
    }
    
    FALLBACK_RESPONSES = {
        'uwu': ['UwU~', '*ribbit*', 'Froggy~'],
        'owo': ['OwO!', '*hop*', 'Kero!']
    }

    GENERATION_CONFIG = {
        "max_output_tokens": 50,
    }

    SAFETY_SETTINGS = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    
    def __init__(self, bot):
        self.bot = bot
        self.fallback_responses = self.FALLBACK_RESPONSES
        self.last_used = {'uwu': None, 'owo': None}
        api_key = config.read().get('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("Google API key not found in config")
        genai.configure(api_key=api_key)
        self.gemini_model = genai.GenerativeModel("gemini-2.0-flash")

    async def get_message_history(self, current_message, scan_limit=10, max_history_items=4):
        raw_messages = []
        async for msg in current_message.channel.history(limit=scan_limit, before=current_message):
            raw_messages.append(msg)
        raw_messages.reverse()
        if not raw_messages:
            return []
        merged_history = []
        for msg in raw_messages:
            role = None
            if msg.author.bot:
                role = "model"
            else:
                role = "user"
            if merged_history and merged_history[-1]["role"] == role:
                merged_history[-1]["parts"][0] += "\n" + msg.content
            else:
                merged_history.append({"role": role, "parts": [msg.content]})
        return merged_history[-max_history_items:]

    async def generate_response(self, response_type, current_user_message_content, history_list):
        try:
            api_messages = list(history_list)
            api_messages.append({"role": "user", "parts": [current_user_message_content]})
            system_prompt_text = self.SYSTEM_PROMPTS[response_type]
            system_instruction_obj = genai.types.ContentDict(
                parts=[genai.types.PartDict(text=system_prompt_text)]
            )
            response = self.gemini_model.generate_content(
                contents=api_messages,
                system_instruction=system_instruction_obj,
                generation_config=self.GENERATION_CONFIG,
                safety_settings=self.SAFETY_SETTINGS
            )
            return response.text.strip()
        except Exception as e:
            print(f"Gemini API error: {e}")
            return random.choice(self.fallback_responses[response_type])

    async def send_response(self, message, response_type):
        history_list = await self.get_message_history(message)
        new_response = await self.generate_response(response_type, message.content, history_list)
        if new_response == self.last_used[response_type]:
            new_response = await self.generate_response(response_type, message.content, history_list)
        self.last_used[response_type] = new_response
        await message.reply(new_response)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        content_lower = message.content.lower()
        if 'uwu' in content_lower:
            await self.send_response(message, 'uwu')
        elif 'owo' in content_lower:
            await self.send_response(message, 'owo')

def setup(bot):
    bot.add_cog(KawaiiReactionsCog(bot)) 