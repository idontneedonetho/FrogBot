# modules.reactions.kawaii_reactions

from modules.utils.commons import pull_history_lines
from disnake.ext import commands
from openai import OpenAI
from core import config
import logging
import disnake


# llm initialization is now deferred to use config

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
        lines = await pull_history_lines(message.channel, limit=10)

        try:
            ollama_url = config.read().get('OLLAMA_BASE_URL', 'http://localhost:11434/v1/')
            llm = OpenAI(base_url=ollama_url, api_key="ollama")
            response = llm.responses.create(
                model='gemma3:1b',
                input='Respond in a cute, kawaii way to these messages:\n' + '\n'.join(lines),
            )
            return response.output_text
        except Exception as e:
            logging.error(f"LLM error: {e}")
            return "UwU! Something went wrong~"

def setup(bot):
    bot.add_cog(KawaiiReactionsCog(bot))