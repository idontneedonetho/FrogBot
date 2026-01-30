# modules.summarize

from modules.utils.commons import get_history_context
from disnake import Embed, Color
from disnake.ext import commands
from openai import OpenAI
from core import config
import disnake
import logging

class SummarizeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        ollama_url = config.read().get('OLLAMA_BASE_URL', 'http://localhost:11434/v1/')
        self.llm = OpenAI(base_url=ollama_url, api_key="ollama")

    @commands.slash_command(name="summarize", description="Summarise recent messages (up to ~8k tokens)")
    async def summarize(self, inter: disnake.ApplicationCommandInteraction):

        await inter.response.defer(ephemeral=True)
        chat_context = await get_history_context(inter.channel, 8192)

        if not chat_context:
            return await inter.edit_original_response(content="No messages to summarise.")

        try:
            response = self.llm.responses.create(
                model='gemma3:1b',
                temperature=0.0,
                input=(
                    "You are a professional secretary. "
                    "Read the provided chat logs and write a formal, paragraph-style summary. "
                    "Output ONLY the summary text. Do not include any introductory sentences, meta-talk, or descriptions of your task. "
                    "Start your response immediately with the first sentence of the summary.\n\n"
                    f"Current Chat History:\n{chat_context}\n\n"
                    "Summary:"
                ),
            )
        except Exception as e:
            logging.error(f"LLM error: {e}")
            return await inter.edit_original_response(content="Failed to generate summary.")
        embed = Embed(title="Conversation Summary", description=response.output_text, color=Color.blue())
        embed.set_footer(text="Summarised chronological history (~8k tokens)")
        await inter.edit_original_response(embed=embed)

def setup(bot):
    bot.add_cog(SummarizeCog(bot))