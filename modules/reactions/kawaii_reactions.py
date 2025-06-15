# modules.reactions.kawaii_reactions

from llama_index.core.output_parsers import PydanticOutputParser
from llama_index.core.chat_engine.utils import ChatMessage
from llama_index.llms.google_genai import GoogleGenAI
from modules.utils.commons import pull_history_lines
from typing import Literal, Dict
from disnake.ext import commands
from pydantic import BaseModel
from core import config
import asyncio
import logging
import disnake
import random

STYLE = Literal["uwu", "owo"]

STYLE_DESC: Dict[STYLE, str] = {
    "uwu": "shy uwu-speak with frog sounds, tildes (~), and emojis",
    "owo": "energetic owo-speak with frog sounds, *actions*, and emojis",
}
FALLBACKS: Dict[STYLE, list[str]] = {
    "uwu": ["UwU~", "*ribbit*", "kero~"],
    "owo": ["OwO!", "*hop*", "kero!"],
}

class _Out(BaseModel):
    reply: str

_PARSER = PydanticOutputParser(_Out)
_FMT = _PARSER.get_format_string()
_LLM = GoogleGenAI(model_name="gemini-2.0-flash", api_key = config.read().get("GOOGLE_API_KEY"))

class KawaiiReactionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last: Dict[STYLE, str | None] = {"uwu": None, "owo": None}

    async def _ask(self, style: STYLE, lines: list[str]) -> str | None:
        sys_prompt = (
            f"You are a kawaii talking frog. Respond using {STYLE_DESC[style]}. "
            f"Max 50 characters. {_FMT}"
        )
        msgs = [ChatMessage(role="system", content=sys_prompt)] + [ChatMessage(role="user", content=l) for l in lines]
        try:
            raw = (await _LLM.achat(msgs) if hasattr(_LLM, "achat") else await asyncio.to_thread(_LLM.chat, msgs)).message.content
            return _PARSER.parse(raw).reply.strip()
        except Exception as e:
            logging.debug("Kawaii LLM error: %s", e)
            return None

    async def _reply(self, msg: disnake.Message, style: STYLE) -> str:
        lines = list(reversed(await pull_history_lines(msg.channel, 3)))
        if msg.content and msg.content not in lines:
            lines.append(msg.content)
        text = await self._ask(style, lines) or random.choice(FALLBACKS[style])
        if text == self._last[style]:
            text = random.choice([t for t in FALLBACKS[style] if t != text])
        self._last[style] = text
        return text

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.id == self.bot.user.id:
            return
        style: STYLE | None = None
        low = message.content.lower()
        if "uwu" in low:
            style = "uwu"
        elif "owo" in low:
            style = "owo"
        if not style:
            return
        await message.reply(await self._reply(message, style))

def setup(bot):
    bot.add_cog(KawaiiReactionsCog(bot)) 