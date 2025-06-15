# modules.summarize

from llama_index.llms.google_genai import GoogleGenAI
from modules.utils.commons import pull_history_lines
from disnake import Embed, Color
from disnake.ext import commands
from core import config
import disnake
import logging

class SummarizeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(name="summarize", description="Summarise recent messages (default 25, max 50)")
    async def summarize(self, inter: disnake.ApplicationCommandInteraction, num_messages: commands.Range[int, 1, 50] = 25):
        await inter.response.defer(ephemeral=True)
        lines = await pull_history_lines(inter.channel, num_messages)
        if not lines:
            return await inter.edit_original_response(content="No messages to summarise.")
        if GoogleGenAI is None:
            return await inter.edit_original_response(content="Missing dependencies: install llama_index and google-generativeai.")
        api_key = config.read().get("GOOGLE_API_KEY")
        if not api_key:
            return await inter.edit_original_response(content="Google API key not configured. Use the control panel or update your config.yaml.")
        llm = GoogleGenAI(model_name="models/gemini-2.0-flash", api_key=api_key)
        prompt = "Summarise the following Discord conversation in under 200 words:\n\n" + "\n".join(lines) + "\n\nSummary:"
        try:
            summary = llm.complete(prompt).text
        except Exception as e:
            logging.error(f"LLM error: {e}")
            return await inter.edit_original_response(content="Failed to generate summary.")
        embed = Embed(title="Conversation Summary", description=summary, color=Color.blue())
        embed.set_footer(text=f"Summarised last {len(lines)} messages (chronological order)")
        await inter.edit_original_response(embed=embed)

def setup(bot):
    bot.add_cog(SummarizeCog(bot)) 