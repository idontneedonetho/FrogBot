# modules.reactions.kawaii_reactions

from llama_index.core.output_parsers import PydanticOutputParser
from llama_index.core.chat_engine.utils import ChatMessage
from llama_index.llms.google_genai import GoogleGenAI
from modules.utils.commons import pull_history_lines
from disnake.ext import commands
from pydantic import BaseModel
from core import config
import asyncio
import logging
import disnake
import random

class _Out(BaseModel):
    reply: str

_PARSER = PydanticOutputParser(_Out)
_FMT = _PARSER.get_format_string()
_LLM = GoogleGenAI(model_name="gemini-2.0-flash", api_key=config.read().get("GOOGLE_API_KEY"))

FALLBACKS = ["UwU~", "OwO!", "kero~", "*ribbit*"]

class KawaiiReactionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last: str | None = None

    async def _ask(self, lines: list[str]) -> str | None:
        sys_prompt = (
            "You are a cute frog. Reply to the user in ≤50 characters, "
            "extra kawaii, with emoticons if you like. "
            f"{_FMT}"
        )
        msgs = [ChatMessage(role="system", content=sys_prompt)] + [ChatMessage(role="user", content=l) for l in lines]
        try:
            raw = (await _LLM.achat(msgs) if hasattr(_LLM, "achat") else await asyncio.to_thread(_LLM.chat, msgs)).message.content
            return _PARSER.parse(raw).reply.strip()
        except Exception as e:
            logging.debug("Kawaii LLM error: %s", e)
            return None

    async def _build_reply(self, msg: disnake.Message) -> str:
        lines = list(reversed(await pull_history_lines(msg.channel, 3)))
        if msg.content:
            lines.append(msg.content)
        text = await self._ask(lines) or random.choice(FALLBACKS)
        if text == self._last:
            text = random.choice([t for t in FALLBACKS if t != text])
        self._last = text
        return text

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.id == self.bot.user.id:
            return
        content_lower = message.content.lower()
        if "uwu" not in content_lower and "owo" not in content_lower:
            return
        await message.reply(await self._build_reply(message))

def setup(bot):
    bot.add_cog(KawaiiReactionsCog(bot)) 