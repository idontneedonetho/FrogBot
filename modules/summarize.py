# modules.summarize

from modules.utils.commons import pull_history_lines
from disnake import Embed, Color
from disnake.ext import commands
from openai import OpenAI
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

        try:
            ollama_url = config.read().get('OLLAMA_BASE_URL', 'http://localhost:11434/v1/')
            llm = OpenAI(base_url=ollama_url, api_key="ollama")
            chat_context = "\n".join(lines)
            response = llm.responses.create(
                model='qwen2.5:1.5b',
                temperature=0.0,
                input=(
                    "You are a professional secretary. "
                    "Read the provided chat logs and write a formal, paragraph-style summary. "
                    "Output ONLY the summary text. Do not include any introductory sentences, meta-talk, or descriptions of your task. "
                    "Start your response immediately with the first sentence of the summary."
                    f"Current Chat History:\n{chat_context}\n\n"
                ),
            )
        except Exception as e:
            logging.error(f"LLM error: {e}")
            return await inter.edit_original_response(content="Failed to generate summary.")
        
        embed = Embed(title="Conversation Summary", description=response.output_text, color=Color.blue())
        embed.set_footer(text=f"Summarised last {len(lines)} messages (chronological order)")
        await inter.edit_original_response(embed=embed)

def setup(bot):
    bot.add_cog(SummarizeCog(bot))