# modules.summarize

from modules.utils.commons import pull_history_lines
from disnake import Embed, Color
from disnake.ext import commands
from openai import OpenAI
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
        
        llm = OpenAI(base_url="http://localhost:11434/v1/", api_key="ollama")

        try:
            response = llm.responses.create(
                # model="granite4:1b-h",
                model='gemma3:1b',
                input='Summarize the following conversation in a concise manner:\n\n' + '\n'.join(lines),
            )
        except Exception as e:
            logging.error(f"LLM error: {e}")
            return await inter.edit_original_response(content="Failed to generate summary.")
        
        embed = Embed(title="Conversation Summary", description=response.output_text, color=Color.blue())
        embed.set_footer(text=f"Summarised last {len(lines)} messages (chronological order)")
        await inter.edit_original_response(embed=embed)

def setup(bot):
    bot.add_cog(SummarizeCog(bot))