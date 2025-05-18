# modules.wiki_search

from deepwiki.deepwiki import DeepWikiClient, QueryResponse
from modules.utils import commons, database as db
from disnake.ext import commands
from typing import Optional
import disnake
import asyncio
import logging

logger = logging.getLogger(__name__)

class WikiSearch(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.client = DeepWikiClient()
        self._processing_lock = asyncio.Lock()
        self._queue_processor_task = None

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("WikiSearch cog is ready, starting queue processor.")
        self.start_queue_processor()

    def cog_unload(self):
        if self._queue_processor_task:
            self._queue_processor_task.cancel()

    def start_queue_processor(self):
        if self._queue_processor_task is None or self._queue_processor_task.done():
            self._queue_processor_task = asyncio.create_task(self._process_queue_loop())
            logger.info("Wiki search queue processor task (re)started.")

    async def _process_queue_loop(self):
        while True:
            try:
                await self._process_single_queue_item()
                queued_count = await db.get_wiki_queued_count()
                processing_count = await db.get_wiki_processing_count()
                if queued_count > 0 or processing_count > 0:
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(10)
            except asyncio.CancelledError:
                logger.info("Wiki search queue processor task cancelled.")
                break
            except Exception as e:
                logger.error(f'Error in wiki queue processor loop: {e}', exc_info=True)
                await asyncio.sleep(60)

    async def _process_single_queue_item(self):
        if self._processing_lock.locked():
            return
        async with self._processing_lock:
            request_data = await db.get_oldest_queued_wiki_request()
            if not request_data:
                return
            request_id = request_data["id"]
            user_id = request_data["user_id"]
            channel_id = request_data["channel_id"]
            query_text = request_data["query_text"]
            original_message_id = request_data["message_id"]
            q_message = None
            logger.info(f"Processing wiki request ID: {request_id} for user {user_id} - Query: '{query_text}'")
            original_channel = self.bot.get_channel(channel_id)
            if not original_channel:
                logger.warning(f'Original channel {channel_id} not found for request {request_id}. Marking as failed.')
                await db.update_wiki_request_status(request_id, "failed", details="Original channel not found.")
                user = self.bot.get_user(user_id)
                if user:
                    try:
                        await user.send(f'Sorry, I couldn\'t process your wiki search "{query_text}" because the original channel is no longer accessible.')
                    except disnake.HTTPException:
                        logger.warning(f'Failed to DM user {user_id} about missing channel for request {request_id}')
                return
            try:
                if original_message_id:
                    try:
                        q_message = await original_channel.fetch_message(original_message_id)
                        if q_message:
                            await q_message.edit(content=f':hourglass_flowing_sand: Processing your wiki search:\n```\n{query_text}\n```\nThis may take a few minutes. I\'ll tag you when it\'s done!')
                    except disnake.NotFound:
                        logger.warning(f'Queue confirmation message {original_message_id} not found for request {request_id}.')
                        q_message = None
                    except disnake.HTTPException as e:
                        logger.warning(f'Failed to edit queue confirmation message {original_message_id}: {e}')
                response: Optional[QueryResponse] = await asyncio.to_thread(
                    self.client.query,
                    search_terms=query_text,
                    context=""
                )
                if response and response.done:
                    format_options = {
                        'query_response': response,
                        'display_raw': False,
                        'display_filtered': True,
                        'filter_show_text': True,
                        'filter_show_markers': False,
                        'filter_show_newlines': False,
                        'display_references': True,
                        'display_query_id': False,
                        'display_query_url': True
                    }
                    formatted_output = await asyncio.to_thread(self.client.format_query_response, **format_options)
                    if formatted_output:
                        logger.info(f'Successfully processed wiki request ID: {request_id}. Sending response.')
                        sent_messages = None
                        tagged_output = f':white_check_mark: <@{user_id}>, your wiki search results:\n```\n{query_text}\n```\n{formatted_output}'
                        if q_message:
                            sent_messages = await commons.send_long_message(original_channel, tagged_output, should_reply=False)
                            try:
                                await q_message.delete()
                            except disnake.HTTPException as e:
                                logger.warning(f'Failed to delete processing message {original_message_id}: {e}')
                        else:
                            logger.warning(f"q_message (ID: {original_message_id}) not available for request {request_id}. Sending to channel directly.")
                            sent_messages = await commons.send_long_message(original_channel, tagged_output, should_reply=False)
                        result_message_id = sent_messages[0].id if sent_messages and len(sent_messages) > 0 else None
                        await db.update_wiki_request_status(request_id, "completed", result_message_id=result_message_id)
                    else:
                        logger.warning(f'Wiki request ID: {request_id} processed but yielded no formatted output.')
                        await db.update_wiki_request_status(request_id, "failed", details="Query successful but no output to display.")
                        await commons.send_message(original_channel, f':warning: <@{user_id}>, your wiki search:\n```\n{query_text}\n```\ncompleted but produced no results to display.', False)
                else:
                    logger.error(f'Wiki query failed or did not complete for request ID: {request_id}.')
                    await db.update_wiki_request_status(request_id, "failed", details="DeepWiki query failed or timed out.")
                    await commons.send_message(original_channel, f':x: <@{user_id}>, there was an error processing your wiki search:\n```\n{query_text}\n```\nPlease try again later.', False)
            except Exception as e:
                logger.error(f'Unhandled error processing wiki request ID {request_id}: {e}', exc_info=True)
                await db.update_wiki_request_status(request_id, "error", details=str(e))
                try:
                    await commons.send_message(original_channel, f':x: <@{user_id}>, an unexpected error occurred while processing your wiki search:\n```\n{query_text}\n```\nThe developers have been notified.', False)
                except Exception as send_e:
                    logger.error(f'Failed to send error message for request {request_id}: {send_e}')

    @commands.slash_command(name="wiki_search", description="Search the wiki using DeepWiki.")
    async def wiki_search_command(self, inter: disnake.ApplicationCommandInteraction, query: str):
        await inter.response.defer()
        current_queued_count = await db.get_wiki_queued_count()
        if current_queued_count >= 20:
            await inter.followup.send(":hourglass: The wiki search queue is currently very long. Please try again in a few minutes.", ephemeral=True)
            return
        confirm_message = None
        try:
            confirm_message = await inter.followup.send(f':page_facing_up: Your wiki search has been queued:\n```\n{query}\n```\nThis may take a few minutes. I\'ll tag you when it\'s done!', wait=True)
        except disnake.HTTPException as e:
            logger.error(f'Failed to send initial confirmation for wiki search by {inter.author.id}: {e}')
            await inter.followup.send("Sorry, I couldn't queue your request right now due to a communication issue. Please try again.", ephemeral=True)
            return
        confirm_message_id = confirm_message.id if confirm_message else None
        request_id = await db.add_to_wiki_queue(
            user_id=inter.author.id,
            guild_id=inter.guild.id if inter.guild else 0,
            channel_id=inter.channel.id,
            query_text=query,
            message_id=confirm_message_id
        )
        if request_id:
            processing_now_count = await db.get_wiki_processing_count()
            current_item_position = await db.get_wiki_queue_position(request_id)
            base_query_text = f'Your wiki search for "{query}"'
            current_status_msg = f'{base_query_text} has been queued!'
            if current_item_position == 1:
                if processing_now_count == 0:
                    current_status_msg = f':hourglass_flowing_sand: {base_query_text} is now being processed...'
                else:
                    current_status_msg = f'{base_query_text} is next in line!'
            elif current_item_position and current_item_position > 1:
                current_status_msg = f'{base_query_text} has been queued! You are number {current_item_position} in the queue.'
            if confirm_message:
                await confirm_message.edit(content=current_status_msg)
            else:
                await inter.channel.send(current_status_msg)
            if not self._processing_lock.locked():
                 asyncio.create_task(self._process_single_queue_item())
            self.start_queue_processor() 
        else:
            error_msg = f'Sorry, <@{inter.author.id}>, I couldn\'t queue your wiki search for "{query}". Please try again later.'
            if confirm_message:
                await confirm_message.edit(content=error_msg)
            else:
                await inter.followup.send(error_msg, ephemeral=True)

def setup(bot: commands.Bot):
    bot.add_cog(WikiSearch(bot))
    logger.info("WikiSearch cog has been loaded.") 