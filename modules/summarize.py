# modules.summarize

from modules.utils.commons import get_history_context
from disnake import Embed, Color
from disnake.ext import commands
from google.genai import types
from google import genai
from core import config
import disnake
import logging

class SummarizeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(name="summarize", description="Summarise recent messages (up to ~8k tokens)")
    async def summarize(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer(ephemeral=True)
        chat_context = await get_history_context(inter.channel, 8192)
        if not chat_context:
            return await inter.edit_original_response(content="No messages to summarise.")
        try:
            api_key = config.read().get("GOOGLE_API_KEY")
            if not api_key:
                return await inter.edit_original_response(content="Google API key missing.")
            client = genai.Client(api_key=api_key)
            system_instruction = (
                "You are a professional secretary. "
                "Read the provided chat logs and write a formal, paragraph-style summary. "
                "Output ONLY the summary text. Do not include any introductory sentences, meta-talk, or descriptions of your task. "
                "Start your response immediately with the first sentence of the summary."
            )
            prompt = f"Current Chat History:\n{chat_context}\n\nSummary:"
            response = await client.aio.models.generate_content(
                model='gemini-3-flash-preview',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    thinking_config=types.ThinkingConfig(thinking_level="minimal")
                )
            )
            summary_text = response.text
        except Exception as e:
            logging.error(f"LLM error: {e}")
            return await inter.edit_original_response(content="Failed to generate summary.")
        embed = Embed(title="Conversation Summary", description=summary_text, color=Color.blue())
        embed.set_footer(text="Summarised chronological history (~8k tokens)")
        await inter.edit_original_response(embed=embed)

def setup(bot):
    bot.add_cog(SummarizeCog(bot))