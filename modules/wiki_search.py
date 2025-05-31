# modules.wiki_search

from modules.utils import commons, database as db
from deepwiki.deepwiki import DeepWikiClient
from disnake.ext import commands
from typing import Union
import disnake
import asyncio
import logging

logger = logging.getLogger(__name__)

class WikiSearch(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client = DeepWikiClient()
        self._queue_processor_task = None
        self.bot.loop.create_task(self._start_queue_processor())

    async def _start_queue_processor(self):
        await self.bot.wait_until_ready()
        self._queue_processor_task = asyncio.create_task(self._process_queue_loop())

    def cog_unload(self):
        if self._queue_processor_task:
            self._queue_processor_task.cancel()

    async def _process_queue_loop(self):
        while True:
            try:
                request_data = await db.get_oldest_queued_wiki_request()
                if not request_data:
                    await asyncio.sleep(10)
                    continue
                request_id = request_data["id"]
                user_id = request_data["user_id"]
                channel_id = request_data["channel_id"]
                query_text = request_data["query_text"]
                original_message_id = request_data["message_id"]
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    await db.update_wiki_request_status(request_id, "failed", details="Channel not found")
                    continue
                if original_message_id:
                    try:
                        msg = await channel.fetch_message(original_message_id)
                        await msg.edit(content=f':hourglass_flowing_sand: Processing: ```{query_text}```\nThis will take a few minutes. Check back here in a little while.')
                    except (disnake.NotFound, disnake.HTTPException):
                        pass
                try:
                    response = await asyncio.to_thread(
                        self.client.query,
                        search_terms=query_text,
                        context=""
                    )
                    if not response or not response.done:
                        await self._send_error(channel, user_id, query_text, "Query failed")
                        await db.update_wiki_request_status(request_id, "failed")
                        continue
                    if original_message_id:
                        try:
                            original_msg = await channel.fetch_message(original_message_id)
                            await original_msg.edit(content=f':white_check_mark: Processed: ```{query_text}```')
                        except (disnake.NotFound, disnake.HTTPException):
                            pass
                    if not isinstance(channel, disnake.Thread):
                        thread_name = f"Wiki Results: {query_text[:50]}"
                        try:
                            original_msg = await channel.fetch_message(original_message_id)
                            channel = await original_msg.create_thread(name=thread_name)
                        except (disnake.NotFound, disnake.HTTPException):
                            channel = await channel.create_thread(name=thread_name, type=disnake.ChannelType.public_thread)
                    formatted = await asyncio.to_thread(
                        self.client.format_query_response,
                        query_response=response,
                        display_raw=False,
                        display_filtered=True,
                        filter_show_text=True,
                        filter_show_markers=False,
                        filter_show_newlines=False,
                        display_references=True,
                        display_query_id=False,
                        display_query_url=True
                    )
                    if formatted:
                        header = f':white_check_mark: <@{user_id}>, results:\n'
                        messages = await commons.send_long_message(channel, header + formatted, should_reply=False)
                        if messages:
                            await db.update_wiki_request_status(request_id, "completed", result_message_id=messages[0].id)
                    else:
                        await self._send_error(channel, user_id, query_text, "No results found")
                        await db.update_wiki_request_status(request_id, "failed")
                except Exception as e:
                    logger.error(f'Error processing request {request_id}: {e}')
                    await self._send_error(channel, user_id, query_text, "Processing error")
                    await db.update_wiki_request_status(request_id, "error", details=str(e))
                if original_message_id:
                    try:
                        msg = await channel.fetch_message(original_message_id)
                        await msg.delete()
                    except (disnake.NotFound, disnake.HTTPException):
                        pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f'Queue processor error: {e}')
                await asyncio.sleep(60)

    async def _send_error(self, channel, user_id, query_text, error_type):
        messages = {
            "Query failed": f':x: <@{user_id}>, query failed for:\n```{query_text}```',
            "No results found": f':warning: <@{user_id}>, no results for:\n```{query_text}```',
            "Processing error": f':x: <@{user_id}>, error processing:\n```{query_text}```'
        }
        await channel.send(messages.get(error_type, messages["Processing error"]))

    async def _queue_wiki_search(self, interaction_or_message: Union[disnake.ApplicationCommandInteraction, disnake.Message], query: str):
        user = interaction_or_message.author
        channel = interaction_or_message.channel
        if await db.get_wiki_queued_count() >= 20:
            msg = ":hourglass: Queue is full. Please try again later."
            if isinstance(interaction_or_message, disnake.ApplicationCommandInteraction):
                await interaction_or_message.followup.send(msg, ephemeral=True)
            else:
                await channel.send(f"{user.mention} {msg}", delete_after=30)
            return
        queue_msg = None
        try:
            position = await db.get_wiki_queued_count()
            msg = f':hourglass_flowing_sand: Added to queue:\n```{query}```\nYou\'re {"next" if position == 0 else f"position in the queue is {position}"}.'
            if isinstance(interaction_or_message, disnake.ApplicationCommandInteraction):
                await interaction_or_message.response.defer()
                queue_msg = await interaction_or_message.followup.send(msg, wait=True)
            else:
                queue_msg = await channel.send(
                    msg,
                    reference=interaction_or_message if not isinstance(channel, disnake.DMChannel) else None
                )
        except disnake.HTTPException:
            pass
        request_id = await db.add_to_wiki_queue(
            user_id=user.id,
            guild_id=interaction_or_message.guild.id if interaction_or_message.guild else 0,
            channel_id=channel.id,
            query_text=query,
            message_id=queue_msg.id if queue_msg else None
        )
        if not request_id:
            error = f'Sorry <@{user.id}>, failed to queue your search for "{query}"'
            if queue_msg:
                await queue_msg.edit(content=error)
            else:
                await channel.send(error)

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.bot or not self.bot.user.mentioned_in(message):
            return
        query = message.content.replace(f"<@!{self.bot.user.id}>", "").replace(f"<@{self.bot.user.id}>", "").strip()
        if query:
            await self._queue_wiki_search(message, query)

    @commands.slash_command(name="wiki_search", description="Search the wiki using DeepWiki.")
    async def wiki_search_command(self, inter: disnake.ApplicationCommandInteraction, query: str):
        await self._queue_wiki_search(inter, query)

def setup(bot: commands.Bot):
    bot.add_cog(WikiSearch(bot))
    logger.info("WikiSearch cog has been loaded.") 