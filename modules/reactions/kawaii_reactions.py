# modules.reactions.kawaii_reactions

from modules.utils.commons import get_history_context
from disnake.ext import commands
from openai import OpenAI
from core import config
import logging
import disnake

class KawaiiReactionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        ollama_url = config.read().get('OLLAMA_BASE_URL', 'http://localhost:11434/v1/')
        self.llm = OpenAI(base_url=ollama_url, api_key="ollama")

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
            response = self.llm.responses.create(
                model='gemma3:1b',
                temperature=1.0,
                input=(
                    "Persona: You are Froggy-chan, a hyper-energetic and super kawaii frog mascot! 🐸✨\n"
                    "Personality: Extremely cheerful, loves lily pads, and uses lots of frog-themed puns.\n"
                    "Rules:\n"
                    "1. Keep responses to EXACTLY one short sentence.\n"
                    "2. Always include a cute frog emoji (🐸) and at least one kaomoji.\n"
                    "3. Be incredibly enthusiastic and 'uwu' in style.\n\n"
                    f"Chat context:\n{chat_context}\n\n"
                    "Task: React to the last person's message with peak froggy energy!"
                )
            )
            return response.output_text
        except Exception as e:
            logging.error(f"LLM error: {e}")
            return "UwU! Something went wrong~"

def setup(bot):
    bot.add_cog(KawaiiReactionsCog(bot))