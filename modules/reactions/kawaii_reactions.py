# modules.reactions.kawaii_reactions

from modules.utils.commons import get_history_context
from disnake.ext import commands
from google.genai import types
from google import genai
from core import config
import logging
import disnake

class KawaiiReactionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.id == self.bot.user.id:
            return
        content_lower = message.content.lower()
        if "uwu" not in content_lower and "owo" not in content_lower:
            return
        await message.reply(await self._build_reply(message))

    async def _build_reply(self, message: disnake.Message) -> str:
        chat_context = await get_history_context(message.channel, token_limit=1000)
        try:
            api_key = config.read().get("GOOGLE_API_KEY")
            if not api_key:
                return "UwU! I need a key from my lily pad~ (Missing API Key)"
            client = genai.Client(api_key=api_key)
            input_prompt = f"Chat context:\n{chat_context}\n\nTask: React to the last person's message with peak froggy energy!"
            system_instruction = (
                "Persona: You are Froggy-chan, a hyper-energetic and super kawaii frog mascot! 🐸✨\n"
                "Personality: Extremely cheerful, loves lily pads, and uses lots of frog-themed puns.\n"
                "Rules:\n"
                "1. Keep responses to EXACTLY one short sentence.\n"
                "2. Always include a cute frog emoji (🐸) and at least one kaomoji.\n"
                "3. Be incredibly enthusiastic and 'uwu' in style."
            )
            response = await client.aio.models.generate_content(
                model='gemini-3-flash-preview',
                contents=input_prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_level="minimal"),
                    system_instruction=system_instruction
                )
            )
            return response.text
        except Exception as e:
            logging.error(f"LLM error: {e}")
            return "UwU! Something went wrong~"

def setup(bot):
    bot.add_cog(KawaiiReactionsCog(bot))