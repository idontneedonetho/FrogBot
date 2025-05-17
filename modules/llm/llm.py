# modules.llm.llm

from typing import List, Dict, Optional, Tuple, Any
import modules.llm.utils.tools as tool_helpers
from chromadb.utils import embedding_functions
import modules.llm.utils.config as llmconfig
import modules.llm.utils.tools as tools
import modules.llm.utils.utils as utils
from modules.utils import commons
from disnake.ext import commands
from datetime import datetime
from google import genai
from core import config
from PIL import Image
import chromadb
import logging
import asyncio
import disnake
import random
import json
import time
import uuid
import re
from deepwiki.deepwiki import DeepWikiClient
from deepwiki.models import QueryResponse
import collections
from modules.utils import database

logger = logging.getLogger(__name__)
logging.getLogger('disnake').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)
logging.getLogger('chromadb').setLevel(logging.WARNING)

class LLMCog(commands.Cog):
    __slots__ = ('bot', 'genai_client', 'chat_session', 'chroma_client', 'notes_collection', 
                 'gemini_embedding_function', 'last_message_canceled', 'message_history', 'frogpilot_wiki_client',
                 'wiki_search_queue', 'is_wiki_search_active', '_current_active_query')

    def __init__(self, bot):
        self.bot = bot
        self.logger = logger
        self.logger.info("Initializing LLM Cog...")
        self.gemini_api_key = config.read().get('GOOGLE_API_KEY')
        if not self.gemini_api_key:
            self.logger.error("Google API key not found in config. LLM features will be disabled.")
            return
        self.genai_client: Optional[genai.Client] = None
        self.chat_session: Optional[Any] = None
        self.chroma_client: Optional[chromadb.Client] = None
        self.notes_collection: Optional[chromadb.Collection] = None
        self.gemini_embedding_function: Optional[embedding_functions.GoogleGenerativeAiEmbeddingFunction] = None
        self.last_message_canceled: bool = False
        self.message_history: List[genai.types.Part] = []
        self.frogpilot_wiki_client: Optional[DeepWikiClient] = None
        self.wiki_search_queue = collections.deque()
        self.is_wiki_search_active: bool = False
        self._current_active_query: Optional[str] = None

    async def cog_load(self):
        if not self.gemini_api_key:
            self.logger.error("LLM Cog cannot load: Google API key is missing.")
            return

        self.logger.info("LLM Cog loading: Initializing external services...")

        try:
            self.genai_client = genai.Client(api_key=self.gemini_api_key)
            self.logger.info("Google GenAI Client initialized successfully.")
        except Exception as e:
            self.logger.error(f"Failed to initialize Google GenAI Client: {e}")
            self.genai_client = None

        self.logger.info("Initializing FrogPilot Wiki Client...")
        try:
            self.frogpilot_wiki_client = DeepWikiClient()
            self.logger.info("FrogPilot Wiki Client initialized successfully.")
        except Exception as e:
            self.logger.error(f"Failed to initialize FrogPilot Wiki Client: {e}", exc_info=True)
            self.frogpilot_wiki_client = None

        if self.genai_client:
            self.logger.info("Initializing Vector DB (ChromaDB & Gemini Embedding Function)...")
            try:
                self.gemini_embedding_function = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
                    api_key=self.gemini_api_key,
                    model_name=llmconfig.EMBEDDING_MODEL_NAME
                )
                self.chroma_client = chromadb.PersistentClient(path=llmconfig.CHROMA_DB_PATH)
                self.notes_collection = self.chroma_client.get_or_create_collection(
                    name=llmconfig.NOTE_COLLECTION_NAME,
                    embedding_function=self.gemini_embedding_function
                )
                self.logger.info(f"ChromaDB client initialized. Collection '{llmconfig.NOTE_COLLECTION_NAME}' loaded/created.")
            except Exception as e:
                self.logger.error(f"Failed to initialize ChromaDB or collections: {e}")
                self.chroma_client = None
                self.notes_collection = None
                self.gemini_embedding_function = None
        else:
            self.logger.warning("Skipping Vector DB initialization because Google GenAI Client is not available.")
        if not self.notes_collection:
            self.logger.warning("Note collection failed to initialize or was skipped. Note-related features will be disabled.")
        self.logger.info("LLM Cog core services initialization complete in cog_load.")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.genai_client:
            self.logger.warning("Cannot initialize main Gemini chat session: GenAI client is not available.")
            return
        try:
            system_instruction = llmconfig.get_formatted_system_prompt(self.bot.user.display_name)
            self.chat_session = self.genai_client.chats.create(
                model=llmconfig.CHAT_MODEL_NAME,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    safety_settings=llmconfig.SAFETY_SETTINGS,
                    tools=[tools.all_tools]
                )
            )
            self.message_history = []
            self.logger.info("Main Gemini chat session initialized successfully.")
        except Exception as e:
            self.logger.error(f"Failed to initialize main Gemini chat session: {e}")
            self.chat_session = None

    async def process_single_message(self, message: disnake.Message):
        try:
            contents, has_video = await self.process_media_content(message)
            self.logger.info(f"Processing message {message.id}...")
            timeout = llmconfig.VIDEO_TIMEOUT if has_video else llmconfig.DEFAULT_TIMEOUT
            current_turn_content = []
            if self.message_history:
                current_turn_content.extend(self.message_history)
            current_turn_content.extend(contents)
            if len(current_turn_content) > 20:
                self.message_history = current_turn_content[-20:]
                self.logger.debug("Trimmed combined message history to last 20 parts for this turn")
            else:
                self.message_history = current_turn_content
            response = await self.generate_content_with_timeout(
                message=message,
                chat_session=self.chat_session,
                contents=self.message_history,
                timeout=timeout
            )
            if response:
                await self.handle_gemini_response(message, response)
        except Exception as e:
            self.logger.error(f"Error processing message task for {message.id}: {e}", exc_info=True)
            if self.bot.user and self.bot.user.mentioned_in(message):
                try:
                    await message.reply("Something went wrong while processing your message in the background.")
                except disnake.HTTPException:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if not self.bot.user or message.author == self.bot.user or message.guild is None:
            return
        if not self.chat_session:
            self.logger.error("Chat session not initialized. Cannot process message.")
            if message.guild and self.bot.user.mentioned_in(message):
                try:
                    await message.reply("I'm having trouble connecting to my brain right now. Please try again later.")
                except disnake.HTTPException:
                    pass
            return
        asyncio.create_task(self.process_single_message(message), name=f"process_msg_{message.id}")

    async def generate_content_with_timeout(self, message: disnake.Message, chat_session: Any, contents: List, timeout: int) -> Optional[genai.types.GenerateContentResponse]:
        if not chat_session:
            self.logger.error("Chat session is not available for generate_content.")
            return None
        if not contents:
            self.logger.error(f"generate_content_with_timeout called with EMPTY contents list for message {message.id}. Aborting call.")
            return None 
        self.logger.debug(f"--- Contents being sent to Gemini for message {message.id} (Total {len(contents)} parts) ---")
        for i, part in enumerate(contents):
            part_type = type(part).__name__
            part_summary = ""
            if hasattr(part, 'text'):
                part_summary = f"Text: '{part.text[:100]}...'" if len(part.text) > 100 else f"Text: '{part.text}'"
            elif hasattr(part, 'function_call'):
                part_summary = f"FunctionCall: {part.function_call.name}, Args: {dict(part.function_call.args)}"
            elif hasattr(part, 'function_response'):
                part_summary = f"FunctionResponse: {part.function_response.name}, Response: {part.function_response.response}"
            elif isinstance(part, Image.Image):
                part_summary = f"PIL.Image: mode={part.mode}, size={part.size}"
            elif hasattr(part, 'file_data') and part.file_data:
                part_summary = f"FileData: mime_type={part.file_data.mime_type}, uri={part.file_data.file_uri}"
            elif hasattr(part, 'inline_data') and part.inline_data: 
                 part_summary = f"InlineData: mime_type={part.inline_data.mime_type}, data_len={len(part.inline_data.data) if part.inline_data.data else 0}"
            else:
                part_summary = f"Unknown part structure: {str(part)[:100]}..."
            self.logger.debug(f"Part {i+1}/{len(contents)}: Type={part_type}, Summary=[{part_summary}]")
        self.logger.debug("--- End of Contents for Gemini ---")
        try:
            async def api_call():
                loop = asyncio.get_event_loop()
                if not contents: 
                    self.logger.error("Critical: Attempted to send empty contents to chat_session.send_message just before API call. This should have been caught earlier.")
                    return None
                response = await loop.run_in_executor(None, lambda: chat_session.send_message(contents))
                return response
            api_response = await asyncio.wait_for(api_call(), timeout=timeout)
            if api_response:
                self.logger.info(f"Gemini API Response received for MSG ID {message.id}. Analyzing structure...")
                try:
                    if api_response.candidates:
                        self.logger.info(f"  API RSP Candidates: {len(api_response.candidates)} for MSG ID {message.id}")
                        for idx, cand in enumerate(api_response.candidates):
                            self.logger.info(f"    API RSP Candidate {idx+1} for MSG ID {message.id}:")
                            if cand.content and cand.content.parts:
                                self.logger.debug(f"      Content Parts count: {len(cand.content.parts)}")
                            else:
                                self.logger.info(f"      Content OR Parts ARE EMPTY/NONE for Candidate {idx+1}. Has Content: {cand.content is not None}. MSG ID {message.id}")
                            safety_ratings_str = "N/A"
                            if hasattr(cand, 'safety_ratings') and cand.safety_ratings:
                                 safety_ratings_str = str([(sr.category.name, sr.probability.name) for sr in cand.safety_ratings])
                            self.logger.info(f"      Safety Ratings: {safety_ratings_str} for MSG ID {message.id}")
                            finish_reason_str = "N/A"
                            if hasattr(cand, 'finish_reason') and cand.finish_reason is not None:
                                finish_reason_str = f"{cand.finish_reason.name} (Value: {cand.finish_reason.value})"
                            self.logger.info(f"      Finish Reason: {finish_reason_str} for MSG ID {message.id}")
                    else:
                        self.logger.info(f"  API RSP Candidates list: Empty or None for MSG ID {message.id}.")
                    prompt_feedback_block_reason_str = "N/A"
                    prompt_feedback_safety_ratings_str = "N/A"
                    if hasattr(api_response, 'prompt_feedback') and api_response.prompt_feedback:
                        if api_response.prompt_feedback.block_reason:
                            prompt_feedback_block_reason_str = str(api_response.prompt_feedback.block_reason.name)
                        if api_response.prompt_feedback.safety_ratings:
                            prompt_feedback_safety_ratings_str = str([(sr.category.name, sr.probability.name) for sr in api_response.prompt_feedback.safety_ratings])
                    self.logger.info(f"  Prompt Feedback: BlockReason='{prompt_feedback_block_reason_str}', SafetyRatings='{prompt_feedback_safety_ratings_str}' for MSG ID {message.id}")
                except Exception as log_ex:
                    self.logger.error(f"Error during detailed logging of API response for MSG ID {message.id}: {log_ex}", exc_info=True)
            else:
                self.logger.warning(f"Gemini API Response object was None for MSG ID {message.id}")
            self.logger.debug("--- End of API Response Log ---")
            return api_response
        except asyncio.TimeoutError:
            self.logger.error(f"Gemini API request timed out after {timeout}s for message {message.id}")
            return None
        except Exception as e:
            self.logger.error(f"Error generating content for message {message.id}: {e}", exc_info=True)
            self.logger.error(f"Problematic contents details logged above for message {message.id}.")
            if self.bot.user and self.bot.user.mentioned_in(message):
                try:
                    await message.channel.send(f"Sorry, I encountered a critical error while trying to process that (request ID: {message.id}).")
                except disnake.HTTPException as discord_err:
                    self.logger.error(f"Failed to send critical error message to Discord: {discord_err}")
            return None

    async def _build_reply_chain_context(self, message: disnake.Message) -> str:
        reply_context_str = ""
        if message.reference and message.reference.message_id:
            reply_chain_messages = []
            current_msg_in_chain = message
            depth = 0
            while depth < llmconfig.MAX_REPLY_DEPTH and current_msg_in_chain.reference and current_msg_in_chain.reference.message_id:
                ref = current_msg_in_chain.reference
                ref_msg = ref.resolved
                if not ref_msg:
                    try:
                        ref_msg = await message.channel.fetch_message(ref.message_id)
                    except (disnake.NotFound, disnake.Forbidden):
                        self.logger.warning(f"Could not fetch referenced message {ref.message_id} at depth {depth}. Stopping chain.")
                        break
                    except Exception as e:
                        self.logger.error(f"Error fetching referenced message {ref.message_id} at depth {depth}: {e}")
                        break
                if ref_msg:
                    reply_chain_messages.insert(0, ref_msg)
                    current_msg_in_chain = ref_msg
                    depth += 1
                else:
                    break
            if reply_chain_messages:
                context_parts = []
                for i, msg_in_chain in enumerate(reply_chain_messages):
                    formatted_msg_in_chain = utils.format_discord_message(msg_in_chain, self.bot)
                    label = f"[Replying To Message:]" if i == len(reply_chain_messages) - 1 else f"[Reply Chain Message {i+1}/{len(reply_chain_messages)}:]"
                    context_parts.append(f"{label}\\n{json.dumps(formatted_msg_in_chain, indent=2)}")
                reply_context_str = "\\n\\n".join(context_parts) + "\\n\\n"
                self.logger.info(f"Built reply chain context ({len(reply_chain_messages)} messages) for message {message.id}")
        return reply_context_str

    async def _extract_forwarded_content(self, message: disnake.Message) -> str:
        forward_context_str = ""
        if message.embeds:
            for embed in message.embeds:
                if embed.description and embed.type == 'rich':
                    forward_context_str = f"[Forwarded Message Content:]\\n{embed.description}\\n\\n"
                    self.logger.info(f"Extracted forwarded content from embed for message {message.id}.")
                    break
        return forward_context_str

    async def _get_notes_context(self, query: str, channel_id: int) -> str:
        notes_context = ""
        retrieved_notes = await self.retrieve_relevant_notes(
            query=query,
            channel_id=channel_id,
            n_results=llmconfig.MAX_NOTES
        )
        if retrieved_notes:
            notes_context = "\\n\\n[Relevant Notes Retrieved:]\\n"
            for i, note in enumerate(retrieved_notes):
                note_id = note.get('id', 'N/A')
                distance = note.get('distance')
                distance_str = f"{distance:.4f}" if distance is not None else "N/A"
                timestamp = note.get('timestamp', 'N/A')
                context = note.get('context', 'N/A')
                content = note.get('content', '')
                notes_context += f"[{i+1}] ID={note_id} Dist={distance_str} (Taken {timestamp}, Context: {context}): {content}\\n"
            self.logger.info(f"Retrieved {len(retrieved_notes)} notes for context.")
        return notes_context

    def _get_wiki_status_context(self) -> str:
        ongoing_searches_for_prompt = []
        if self.is_wiki_search_active and self._current_active_query:
            ongoing_searches_for_prompt.append(self._current_active_query)
        queued_queries = [item['query'] for item in self.wiki_search_queue]
        for q_query in queued_queries:
            if not (self.is_wiki_search_active and q_query == self._current_active_query):
                 ongoing_searches_for_prompt.append(q_query)
        ongoing_searches_str = ""
        if ongoing_searches_for_prompt:
            max_shown_queries = 3
            display_queries = ongoing_searches_for_prompt[:max_shown_queries]
            search_list_str = [f"\'{q}\'" for q in display_queries]
            status_parts = []
            if self.is_wiki_search_active and self._current_active_query:
                status_parts.append(f"Currently processing: \'{self._current_active_query}\'")
            if self.wiki_search_queue:
                status_parts.append(f"{len(self.wiki_search_queue)} in queue")
            status_line = " (".join(status_parts) + ")" if status_parts else ""
            ongoing_searches_str = f"\\n\\n[FrogPilot Wiki Status {status_line}: Queries include {{', '.join(search_list_str)}}]"
            if len(ongoing_searches_for_prompt) > max_shown_queries:
                ongoing_searches_str += f" and {len(ongoing_searches_for_prompt) - max_shown_queries} more..."
            self.logger.debug(f"Built wiki status context: {ongoing_searches_str}")
        return ongoing_searches_str

    async def _extract_media_parts_from_message(self, message: disnake.Message) -> Tuple[List[Any], bool]:
        media_parts = []
        has_video = False
        processed_urls = set()
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content)
        for url in urls:
            if url in processed_urls: continue
            media_part = await utils.process_url(url)
            if media_part:
                media_parts.append(media_part)
                processed_urls.add(url)
                if isinstance(media_part, genai.types.Part) and hasattr(media_part, 'file_data') and media_part.file_data:
                    if "video" in media_part.file_data.mime_type.lower():
                        has_video = True
                        self.logger.info(f"Processed video URL: {url}")
                    else:
                        self.logger.info(f"Processed file URL: {url}")
                elif isinstance(media_part, Image.Image):
                    self.logger.info(f"Processed image URL: {url}")
        for attachment in message.attachments:
            if attachment.url in processed_urls: continue
            media_part = await utils.process_media(attachment)
            if media_part:
                media_parts.append(media_part)
                if isinstance(media_part, genai.types.Part) and hasattr(media_part, 'file_data') and media_part.file_data:
                     if "video" in media_part.file_data.mime_type.lower():
                        has_video = True
                elif not isinstance(media_part, Image.Image):
                    has_video = True
                self.logger.info(f"Processed attachment: {attachment.filename}")
        return media_parts, has_video

    async def process_media_content(self, message: disnake.Message) -> Tuple[List[Any], bool]:
        initial_contents = []
        reply_context_str = await self._build_reply_chain_context(message)
        forward_context_str = await self._extract_forwarded_content(message)
        formatted_current_msg = utils.format_discord_message(message, self.bot)
        current_message_context_str = f"[Current Message:]\\n{json.dumps(formatted_current_msg, indent=2)}"
        notes_context_str = await self._get_notes_context(message.content or "", message.channel.id)
        wiki_status_context_str = self._get_wiki_status_context()
        base_prompt_str = llmconfig.get_formatted_system_prompt(self.bot.user.display_name)
        full_prompt = (
            f"{base_prompt_str}"
            f"{notes_context_str}"
            f"{wiki_status_context_str}"
            f"\\n{reply_context_str}"
            f"{forward_context_str}"
            f"{current_message_context_str}"
        )
        initial_contents.append(full_prompt)
        self.logger.debug(f"--- Full Prompt for Message {message.id} ---")
        self.logger.debug(full_prompt)
        self.logger.debug("----------------------------------------")
        media_parts, has_video = await self._extract_media_parts_from_message(message)
        initial_contents.extend(media_parts)
        return initial_contents, has_video

    async def _get_recent_channel_history(self, channel: disnake.abc.Messageable, num_messages: int) -> str:
        history_str = f"Recent messages in #{channel.name} (newest first):\n"
        message_count = 0
        try:
            async for msg in channel.history(limit=num_messages):
                formatted = utils.format_discord_message(msg, self.bot)
                history_str += f"- {formatted['author']}: {formatted['content']}\n"
                message_count += 1
            if message_count == 0:
                history_str += "(No recent messages found or accessible)."
            return history_str
        except disnake.Forbidden:
            self.logger.warning(f"Missing permissions to read history in channel {channel.id}")
            return "(Error: Cannot access channel history due to permissions)."
        except Exception as e:
            self.logger.error(f"Error fetching channel history for {channel.id}: {e}")
            return f"(Error fetching channel history: {e})"

    async def _execute_final_action(self, message: disnake.Message, final_action_call: genai.types.FunctionCall) -> Tuple[bool, Optional[List[genai.types.Part]]]:
        final_action_name = final_action_call.name
        final_action_args = final_action_call.args
        self.logger.info(f"Executing final action: {final_action_name} with args: {dict(final_action_args)}")
        try:
            if final_action_name == "send_message":
                content = final_action_args.get("content", "").strip()
                reply_to_original = final_action_args.get("reply_to_original", False)
                if not content:
                    self.logger.warning("send_message call with empty content. Treating as effectively ignored.")
                    return True, None
                should_send = await self.simulate_typing_and_check_intervention(message, content)
                if should_send:
                    self.logger.info(f"Intervention check passed for {message.id}. Sending message.")
                    content_converted = await utils.convert_mentions(content, message)
                    await commons.send_long_message(message, content_converted, reply_to_original)
                    return True, None
                else:
                    self.logger.info(f"Intervention check failed for {message.id}. Preparing cancellation feedback for LLM.")
                    cancellation_feedback = genai.types.Part(
                        function_response=genai.types.FunctionResponse(
                            name=final_action_name,
                            response={"status": "cancelled_due_to_intervention",
                                      "reason": "A subsequent message likely made the planned response irrelevant or user cancelled."}
                        )
                    )
                    return False, [cancellation_feedback]
            elif final_action_name == "ignore_message":
                self.logger.info("Executing final ignore_message action.")
                return True, None
            else:
                self.logger.warning(f"Unknown final action call: {final_action_name}")
                return True, None
        except Exception as e:
            self.logger.error(f"Error executing final action '{final_action_name}': {e}", exc_info=True)
            if message.guild and self.bot.user and self.bot.user.mentioned_in(message):
                try:
                    await message.reply(f"Oops, something went wrong while performing the final action ({final_action_name}) 😅")
                except disnake.HTTPException:
                    pass
            return True, None

    async def handle_gemini_response(self, message: disnake.Message, response: genai.types.GenerateContentResponse) -> None:
        if not response or not response.candidates:
            self.logger.warning("Gemini response missing or contained no candidates. Doing nothing.")
            return
        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            self.logger.warning("Gemini response candidate missing content or parts. Doing nothing.")
            return
        parts_to_process_from_llm = list(candidate.content.parts)
        final_action_has_executed_this_turn = False
        loop_iterations = 0
        max_loops = 5
        while loop_iterations < max_loops:
            loop_iterations += 1
            self.logger.debug(f"LLM response processing loop: Iteration {loop_iterations}/{max_loops}")
            if not parts_to_process_from_llm and loop_iterations > 1:
                self.logger.debug("No more parts from LLM to process in this iteration.")
                break
            intermediate_tool_calls_identified = []
            potential_final_action_call = None
            for part in parts_to_process_from_llm:
                if part.function_call:
                    action_name = part.function_call.name
                    if action_name in ["send_message", "ignore_message"]:
                        if not potential_final_action_call:
                            potential_final_action_call = part.function_call
                            self.logger.debug(f"Identified potential final action: {action_name}")
                        else:
                            self.logger.warning(f"Multiple final actions ({potential_final_action_call.name}, then {action_name}) proposed by LLM in one turn. Using the first: {potential_final_action_call.name}.")
                    else:
                        intermediate_tool_calls_identified.append(part.function_call)
                        self.logger.debug(f"Identified intermediate tool call: {action_name}")
            current_llm_response_text_parts = [p.text for p in parts_to_process_from_llm if hasattr(p, 'text') and p.text]
            parts_to_process_from_llm = []
            intermediate_responses_to_send_to_llm = []
            any_intermediate_tool_was_identified = bool(intermediate_tool_calls_identified)
            if intermediate_tool_calls_identified:
                for func_call in intermediate_tool_calls_identified:
                    tool_action_name = func_call.name
                    self.logger.info(f"Processing intermediate tool call: {tool_action_name} with args: {dict(func_call.args)}")
                    try:
                        response_part_from_tool = await tool_helpers.process_intermediate_tool_call(self, message, func_call)
                        if response_part_from_tool:
                            intermediate_responses_to_send_to_llm.append(response_part_from_tool)
                    except Exception as e:
                        self.logger.error(f"Critical error during intermediate tool processing '{tool_action_name}': {e}", exc_info=True)
                        intermediate_responses_to_send_to_llm.append(genai.types.Part(
                            function_response=genai.types.FunctionResponse(
                                name=tool_action_name,
                                response={"error": f"Critical failure processing tool: {e}"}
                            )
                        ))
            if intermediate_responses_to_send_to_llm:
                self.logger.info(f"Sending {len(intermediate_responses_to_send_to_llm)} intermediate function result(s) back to the model.")
                try:
                    follow_up_response = await self.generate_content_with_timeout(
                        message=message,
                        chat_session=self.chat_session,
                        contents=intermediate_responses_to_send_to_llm,
                        timeout=llmconfig.DEFAULT_TIMEOUT
                    )
                    if follow_up_response and follow_up_response.candidates:
                        new_candidate = follow_up_response.candidates[0]
                        parts_to_process_from_llm = list(new_candidate.content.parts) if new_candidate.content else []
                        continue
                    else:
                        self.logger.error("Model did not respond after receiving intermediate function results.")
                        if message.guild and self.bot.user and self.bot.user.mentioned_in(message):
                           await message.reply("Something went wrong during multi-step processing (model didn't respond to tool results).")
                        break
                except Exception as e:
                    self.logger.error(f"Error sending intermediate results to Gemini or processing its response: {e}", exc_info=True)
                    if message.guild and self.bot.user and self.bot.user.mentioned_in(message):
                        await message.reply("Oops, encountered an error during multi-step processing.")
                    break
            elif any_intermediate_tool_was_identified:
                self.logger.info("Intermediate tool(s) were processed. None returned data for the LLM. Proceeding to potential final action from original LLM response.")
            if potential_final_action_call:
                action_completed_this_step, feedback_parts_for_llm = await self._execute_final_action(message, potential_final_action_call)

                if feedback_parts_for_llm:
                    self.logger.info("Final action (send_message) was cancelled by intervention. Sending feedback to LLM.")
                    try:
                        intervention_response = await self.generate_content_with_timeout(
                            message=message,
                            chat_session=self.chat_session,
                            contents=feedback_parts_for_llm,
                            timeout=llmconfig.DEFAULT_TIMEOUT
                        )
                        if intervention_response and intervention_response.candidates:
                            new_candidate = intervention_response.candidates[0]
                            parts_to_process_from_llm = list(new_candidate.content.parts) if new_candidate.content else []
                            continue
                        else:
                            self.logger.error("LLM did not respond to intervention cancellation feedback. Breaking loop.")
                            final_action_has_executed_this_turn = True
                            break 
                    except Exception as e:
                        self.logger.error(f"Error sending intervention cancellation feedback to LLM: {e}", exc_info=True)
                        final_action_has_executed_this_turn = True
                        break
                elif action_completed_this_step:
                    final_action_has_executed_this_turn = True
                    break
                else:
                    self.logger.warning("Final action processing returned an unexpected state. Breaking loop.")
                    final_action_has_executed_this_turn = True
                    break
            elif not any_intermediate_tool_was_identified:
                if current_llm_response_text_parts:
                    final_text = "".join(current_llm_response_text_parts).strip()
                    if final_text:
                        self.logger.warning(f"Model returned plain text instead of a function call after {loop_iterations-1} tool iteration(s): '{final_text[:200]}...'")
                else:
                    self.logger.debug("LLM response had no function calls and no text for this iteration.")
                break
            if loop_iterations >= max_loops:
                self.logger.error(f"Max loop iterations ({max_loops}) reached for message {message.id}. Breaking.")
                break
        if not final_action_has_executed_this_turn:
            self.logger.warning(f"LLM processing for message {message.id} completed after {loop_iterations} iteration(s) without an explicit final action (send/ignore) being successfully executed or intervention handled. Defaulting to ignore.")

    async def _perform_intervention_llm_check(self, 
                                              original_message: disnake.Message, 
                                              planned_content: str, 
                                              trigger_message: disnake.Message) -> bool:
        self.logger.info(f"Performing intervention LLM check. Planned: '{planned_content[:50]}...'. Trigger by {trigger_message.author.display_name}: '{trigger_message.content[:50]}...'")
        formatted_trigger_msg = utils.format_discord_message(trigger_message, self.bot)
        history_context_str = ""
        num_history_to_fetch = llmconfig.HISTORY_TURNS_FOR_CHECK * 2 + 1
        try:
            history_messages = []
            async for hist_msg in original_message.channel.history(limit=num_history_to_fetch, before=trigger_message):
                history_messages.append(hist_msg)
            formatted_history = []
            for item in history_messages:
                formatted_item = utils.format_discord_message(item, self.bot)
                author = formatted_item.get('author', 'Unknown')
                content = formatted_item.get('content', '').strip()
                if content:
                    formatted_history.insert(0, f"{author}: {content}") 
            if formatted_history:
                history_context_str = "Recent Channel History (oldest first, leading up to MESSAGE_B):\n" + "\n".join(formatted_history) + "\n\n---\n\n"
                self.logger.debug(f"Added {len(formatted_history)} history messages to intervention check prompt.")
        except disnake.Forbidden:
            self.logger.warning(f"Cannot access history for intervention check in channel {original_message.channel.id}")
            history_context_str = "(Could not retrieve channel history for context due to permissions)\n\n"
        except Exception as hist_err:
            self.logger.warning(f"Could not fetch/format history for intervention check: {hist_err}")
            history_context_str = "(Error retrieving channel history for context)\n\n"
        check_instructions = f"""Analyze the following situation:
1. Your planned message is MESSAGE_A.
2. A new message, MESSAGE_B, has arrived from another user.
3. Consider the Recent Channel History provided for context leading up to MESSAGE_B.

MESSAGE_A (Your planned response to an earlier message): "{planned_content}"
MESSAGE_B (The new message from another user): {json.dumps(formatted_trigger_msg, indent=2)}

**Decision:** Should MESSAGE_A still be sent, or should it be cancelled?

**Rule:** Call `ignore_message` (which means cancel MESSAGE_A) ONLY IF MESSAGE_B meets one of these strict conditions:
    a) Directly contradicts a factual statement in MESSAGE_A.
    b) Answers the *exact same question* or provides the *exact same information* as MESSAGE_A, making MESSAGE_A completely redundant.
    c) Makes MESSAGE_A nonsensical or clearly inappropriate due to a sudden, drastic shift in the immediate conversation confirmed by the content of MESSAGE_B and recent history.

**Otherwise (if none of the above strict conditions are met):** Call `send_message` (which means allow MESSAGE_A to be sent).
Be conservative about cancelling. Do NOT cancel if MESSAGE_B is merely related, adds more context, asks a follow-up question, or discusses a tangent unless it invalidates MESSAGE_A as per the rules above.
"""
        full_check_prompt = history_context_str + check_instructions
        intervention_config = genai.types.GenerateContentConfig(
            safety_settings=llmconfig.SAFETY_SETTINGS,
            tools=[tools.intervention_check_tool]
        )
        if not self.genai_client:
            self.logger.error("GenAI client not available for intervention LLM check. Defaulting to not sending.")
            return False
        temp_chat_for_check = self.genai_client.chats.create(
            model=llmconfig.CHAT_MODEL_NAME,
            config=intervention_config
        )
        self.logger.debug(f"Intervention check prompt for LLM: {full_check_prompt}")
        check_response = await self.generate_content_with_timeout(
            original_message,
            temp_chat_for_check,
            [full_check_prompt],
            llmconfig.CHECK_TIMEOUT
        )
        should_send_planned_message = False
        if check_response and check_response.function_calls:
            for func_call in check_response.function_calls:
                if func_call.name == "send_message":
                    should_send_planned_message = True
                    self.logger.info("Intervention LLM check decided: SEND planned message.")
                    break
                elif func_call.name == "ignore_message":
                    should_send_planned_message = False
                    self.logger.info("Intervention LLM check decided: IGNORE (cancel) planned message.")
                    break
        else:
            self.logger.warning(f"Intervention LLM check failed, timed out, or returned no function call. Defaulting to CANCEL planned message for safety. Trigger message ID: {trigger_message.id}")
            should_send_planned_message = False
        return should_send_planned_message

    async def simulate_typing_and_check_intervention(self, message: disnake.Message, content_to_send: str) -> bool:
        if not content_to_send:
            return True
        if not self.chat_session or not self.genai_client: 
            self.logger.warning("Chat session or GenAI client not available for intervention check. Sending directly.")
            return True
        word_count = len(content_to_send.split())
        actual_wpm = llmconfig.BASE_WPM * (1 + random.uniform(-llmconfig.WPM_VARIANCE, llmconfig.WPM_VARIANCE))
        typing_time = (word_count / actual_wpm) * 60
        if self.last_message_canceled:
            typing_time *= 0.5
        typing_time += random.uniform(0.5, 1.5)
        typing_time = max(typing_time, 1.0)
        typing_task = None
        start_time = time.time()
        self.logger.debug(f"Simulating typing for {typing_time:.2f}s for message {message.id} (planned content: '{content_to_send[:50]}...')")
        try:
            typing_task = asyncio.create_task(message.channel.trigger_typing(), name=f"typing-main-{message.id}")
            while (elapsed_time := time.time() - start_time) < typing_time:
                sleep_duration = min(5.0, typing_time - elapsed_time)
                if sleep_duration <= 0: break
                await asyncio.sleep(sleep_duration)
                if typing_task.done():
                    try:
                        typing_task.result()
                        self.logger.debug(f"Typing task for {message.id} finished normally, restarting if needed.")
                    except asyncio.CancelledError:
                        self.logger.debug(f"Typing task for {message.id} was cancelled, restarting if needed.")
                    except Exception as task_exc:
                        self.logger.warning(f"Typing task for {message.id} failed: {task_exc}", exc_info=False)
                    if (time.time() - start_time) < typing_time:
                         typing_task = asyncio.create_task(message.channel.trigger_typing(), name=f"typing-restart-{message.id}")
                try:
                    async for new_msg in message.channel.history(limit=5, after=message, oldest_first=False):
                        if new_msg.author == self.bot.user: continue
                        self.logger.info(f"Intervention check triggered by new message {new_msg.id} from {new_msg.author.display_name} during typing for original message {message.id}.")
                        
                        self.logger.info(f"Intervention check triggered by new message {new_msg.id} from {new_msg.author.display_name} during typing for original message {message.id}.")
                        should_send_planned_message = await self._perform_intervention_llm_check(
                            original_message=message, 
                            planned_content=content_to_send, 
                            trigger_message=new_msg
                        )
                        if not should_send_planned_message:
                            self.logger.info(f"Intervention check determined to CANCEL planned response for original message {message.id} due to trigger message {new_msg.id}.")
                            self.last_message_canceled = True
                            return False
                        else:
                            self.logger.info(f"Intervention check passed for trigger {new_msg.id}. Continuing typing simulation for original message {message.id}.")
                            break 
                except disnake.HTTPException as hist_err:
                    self.logger.warning(f"Failed to fetch history during typing simulation intervention check: {hist_err}")
                except Exception as check_err:
                    self.logger.error(f"Error during intervention check logic within typing simulation: {check_err}", exc_info=True)
                    self.last_message_canceled = False
                    return True
            self.logger.debug(f"Typing simulation for message {message.id} completed without cancellation.")
            self.last_message_canceled = False
            return True
        finally:
            if typing_task and not typing_task.done():
                typing_task.cancel()
                try:
                    await typing_task
                except asyncio.CancelledError:
                    pass
                except Exception as final_task_exc:
                    self.logger.warning(f"Error awaiting originally cancelled typing task for {message.id}: {final_task_exc}")

    async def save_note(self, note_content: str, context: Optional[str] = None, channel_id: Optional[int] = None, is_global: bool = False):
        if not self.notes_collection:
            self.logger.warning("Notes collection not available. Skipping saving note.")
            return
        note_id = str(uuid.uuid4())
        metadata = {"context": context or "", 
                    "timestamp": datetime.now().isoformat(),
                    "is_global": is_global}
        if not is_global and channel_id is not None: 
            metadata['channel_id'] = str(channel_id) 
        try:
            self.notes_collection.add(
                documents=[note_content],
                metadatas=[metadata],
                ids=[note_id]
            )
            scope = "Global" if is_global else f"Channel {channel_id or 'N/A'}"
            log_message = f"Note Saved (ID: {note_id}, Scope: {scope}): {note_content}"
            if context:
                log_message += f" (Context: {context})"
            self.logger.info(log_message)
        except Exception as e:
            self.logger.error(f"Failed to save note to ChromaDB (ID: {note_id}): {e}")

    async def update_note_content(self, note_id: str, new_content: str, channel_id: Optional[int] = None):
        if not self.notes_collection:
            self.logger.warning(f"Notes collection not available. Skipping update for note {note_id}.")
            return
        try:
            existing_note = self.notes_collection.get(ids=[note_id], include=['metadatas'])
            metadata = {}
            if existing_note and existing_note.get('metadatas') and existing_note['metadatas']:
                metadata = existing_note['metadatas'][0] or {}
            metadata['timestamp'] = datetime.now().isoformat()
            if channel_id is not None:
                metadata['channel_id'] = str(channel_id)
            else:
                metadata.pop('channel_id', None)
            self.notes_collection.update(
                ids=[note_id],
                documents=[new_content],
                metadatas=[metadata]
            )
            self.logger.info(f"Note Updated (ID: {note_id}, Channel: {channel_id or metadata.get('channel_id', 'N/A')}): {new_content}")
        except Exception as e:
            self.logger.error(f"Failed to update note in ChromaDB (ID: {note_id}): {e}")

    async def retrieve_relevant_notes(self, query: str, channel_id: Optional[int] = None, n_results: int = llmconfig.MAX_NOTES) -> List[Dict]:
        if not self.notes_collection:
            self.logger.debug("Notes collection not available for retrieval.")
            return []
        channel_notes = []
        if channel_id is not None:
            try:
                where_filter = {
                    "$and": [
                        {"channel_id": str(channel_id)}, 
                        {"is_global": False}
                    ]
                } 
                self.logger.debug(f"Querying ChromaDB for '{query}' with channel filter: {where_filter}")
                results = self.notes_collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    where=where_filter,
                    include=['documents', 'metadatas', 'distances']
                )
                self.logger.debug(f"ChromaDB channel query results: {results}")
                if results and results.get('ids') and results['ids'][0]:
                    for i, note_id in enumerate(results['ids'][0]):
                        distance = results['distances'][0][i] if results.get('distances') else None
                        doc = results['documents'][0][i]
                        meta = results['metadatas'][0][i]
                        channel_notes.append({
                            "id": note_id,
                            "content": doc,
                            "context": meta.get("context"),
                            "timestamp": meta.get("timestamp"),
                            "distance": distance,
                            "channel_id": meta.get("channel_id"),
                            "is_global": meta.get("is_global", False)
                        })
                self.logger.info(f"Retrieved {len(channel_notes)} channel-specific notes for query.")
            except Exception as e:
                self.logger.error(f"Error retrieving channel-specific notes from ChromaDB for query '{query}': {e}")
        global_notes = []
        num_global_needed = n_results - len(channel_notes)
        if num_global_needed > 0:
             try:
                channel_note_ids = {note['id'] for note in channel_notes}
                where_filter = {"is_global": True}
                self.logger.debug(f"Querying ChromaDB for '{query}' for {num_global_needed} global results (is_global=True).")
                results = self.notes_collection.query(
                    query_texts=[query],
                    n_results=num_global_needed, 
                    where=where_filter, 
                    include=['documents', 'metadatas', 'distances']
                )
                self.logger.debug(f"ChromaDB global query results: {results}")
                if results and results.get('ids') and results['ids'][0]:
                    for i, note_id in enumerate(results['ids'][0]):
                        if note_id in channel_note_ids: continue 
                        distance = results['distances'][0][i] if results.get('distances') else None
                        doc = results['documents'][0][i]
                        meta = results['metadatas'][0][i]
                        global_notes.append({
                            "id": note_id,
                            "content": doc,
                            "context": meta.get("context"),
                            "timestamp": meta.get("timestamp"),
                            "distance": distance,
                            "channel_id": meta.get("channel_id"),
                            "is_global": meta.get("is_global", False)
                        })
                self.logger.info(f"Retrieved {len(global_notes)} additional global notes for query.")
             except Exception as e:
                self.logger.error(f"Error retrieving global notes from ChromaDB for query '{query}': {e}")
        all_notes = channel_notes + global_notes
        all_notes.sort(key=lambda x: x.get('distance') if x.get('distance') is not None else float('inf'))
        final_results = all_notes[:n_results]
        self.logger.info(f"Returning final {len(final_results)} notes (channel+global) for query.")
        return final_results

    async def delete_note(self, note_id: str) -> bool:
        if not self.notes_collection:
            self.logger.warning(f"Notes collection not available. Skipping delete for note {note_id}.")
            return False
        try:
            existing = self.notes_collection.get(ids=[note_id], limit=1)
            if not existing or not existing.get('ids'):
                self.logger.warning(f"Attempted to delete non-existent note (ID: {note_id}).")
                return False
            self.notes_collection.delete(ids=[note_id])
            self.logger.info(f"Note Deleted (ID: {note_id})")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete note from ChromaDB (ID: {note_id}): {e}")
            return False

    def cog_unload(self):
        self.logger.info("LLM Cog unloading. Chroma PersistentClient should handle persistence.")

    async def _execute_search_and_send(self, original_message: disnake.Message, query: str):
        author_mention = original_message.author.mention
        author_id = original_message.author.id
        channel = original_message.channel
        self._current_active_query = query
        self.logger.info(f"Executing FrogPilot Wiki search for query: '{query}' for user {author_id}")
        feedback_msg_content = f"{author_mention}, I'm now processing your request and searching the FrogPilot Wiki for:\n> {query}\nThis might take a moment..."
        try:
            await channel.send(feedback_msg_content)
        except disnake.HTTPException as discord_err:
            self.logger.error(f"Failed to send FrogPilot Wiki processing message: {discord_err}")
        except Exception as e:
            self.logger.error(f"Unexpected error sending FrogPilot Wiki processing message: {e}", exc_info=True)
        wiki_response: Optional[QueryResponse] = None
        try:
            if not self.frogpilot_wiki_client:
                self.logger.error(f"FrogPilot Wiki client not initialized before execution for query '{query}'.")
                await commons.send_long_message(original_message, f"{author_mention}, I can't search the wiki right now because the knowledge base isn't available.")
                return
            loop = asyncio.get_running_loop()
            wiki_response = await loop.run_in_executor(
                None,
                self.frogpilot_wiki_client.query,
                query,
                "" 
            )
            formatted_message_text = ""
            if wiki_response and (wiki_response.raw_answer or wiki_response.references or wiki_response.content_elements):
                self.logger.info(f"FrogPilot Wiki search completed successfully for query: '{query}'.")
                formatted_message_text = f"{author_mention}, here are the FrogPilot Wiki results for your query:\n> {query}\n\n"
                summary_to_use = self.frogpilot_wiki_client.format_query_response(
                    query_response=wiki_response,
                    display_raw=False,
                    display_filtered=True,
                    filter_show_text=True,
                    filter_show_markers=False,
                    filter_show_newlines=True,
                    display_references=False,
                    display_query_id=False,
                    display_query_url=False
                )
                if summary_to_use:
                    summary_to_use = summary_to_use.strip()
                self.logger.debug(f"Formatted summary from DeepWiki for query '{query}':\n------BEGIN FORMATTED WIKI SUMMARY------\n{summary_to_use}\n------END FORMATTED WIKI SUMMARY------")
                if summary_to_use:
                    formatted_message_text += f"# **Summary:**\n{summary_to_use}\n\n"
                elif wiki_response.raw_answer:
                    self.logger.warning(f"Formatted summary for '{query}' was empty/None, but raw_answer had content. Raw answer logged for review: '{wiki_response.raw_answer[:200]}...'")
                if wiki_response.references:
                    from deepwiki.models import Reference
                    formatted_message_text += "**References:**\n"
                    for i, ref_obj in enumerate(wiki_response.references):
                        if isinstance(ref_obj, Reference):
                            raw_link = ref_obj.github_url or "No URL available"
                            link_no_embed = f"<{raw_link}>" if raw_link != "No URL available" else raw_link
                            display_path = ref_obj._path if ref_obj._path else ref_obj.file_path
                            formatted_message_text += f"{i+1}. `{display_path}` ({link_no_embed})\n"
                        else:
                            self.logger.warning(f"Unexpected item in references list: {ref_obj}")
                            formatted_message_text += f"{i+1}. [Unexpected reference format]\n"
                if not summary_to_use and not wiki_response.references and wiki_response.raw_answer:
                    self.logger.info(f"Wiki search for '{query}' had a raw answer but summary extraction and references were empty. Adding raw answer snippet.")
                    formatted_message_text += f"\n**Details from Wiki:**\n{wiki_response.raw_answer[:1000]}...\n(Summary extraction was inconclusive)"
                elif not summary_to_use and not wiki_response.references and not wiki_response.raw_answer:
                     formatted_message_text += "The search completed, but I couldn't extract a clear summary or specific references for your query."
            elif wiki_response:
                self.logger.warning(f"FrogPilot Wiki search for '{query}' for user {author_id} completed but yielded no usable answer or references.")
                formatted_message_text = f"{author_mention}, the FrogPilot Wiki search for '{query}' finished, but I couldn't find specific details or references for that."
            else:
                self.logger.warning(f"FrogPilot Wiki search for '{query}' for user {author_id} returned no response object (it was None).")
                formatted_message_text = f"{author_mention}, sorry, the FrogPilot Wiki search for '{query}' didn't return any results. There might have been an issue with the search service."
            await commons.send_long_message(original_message, formatted_message_text.strip())
            await database.log_wiki_search_event(user_id=author_id, query_text=query, event_type='finished_success', queue_length=len(self.wiki_search_queue))
        except Exception as dw_err:
            self.logger.error(f"Error during _execute_search_and_send for query '{query}' (user {author_id}): {dw_err}", exc_info=True)
            await database.log_wiki_search_event(user_id=author_id, query_text=query, event_type='finished_error', queue_length=len(self.wiki_search_queue), details=str(dw_err))
            try:
                await commons.send_long_message(original_message, f"{author_mention}, sorry, an unexpected error occurred while I was working on your wiki search for '{query}'.")
            except Exception as send_final_err:
                self.logger.error(f"Failed to send final error message to user {author_id} for query '{query}': {send_final_err}")
        finally:
            self._current_active_query = None

    async def _process_wiki_queue(self):
        if self.is_wiki_search_active or not self.wiki_search_queue:
            return
        self.is_wiki_search_active = True
        queued_item = self.wiki_search_queue.popleft()
        original_message_obj: disnake.Message = queued_item['message']
        query: str = queued_item['query']
        self.logger.info(f"Dequeued wiki search for '{query}' from user {original_message_obj.author.id}. Queue length now: {len(self.wiki_search_queue)}")
        await database.log_wiki_search_event(user_id=original_message_obj.author.id, query_text=query, event_type='processing_started_queue', queue_length=len(self.wiki_search_queue) + 1)
        try:
            await self._execute_search_and_send(original_message_obj, query)
        except Exception as e:
            self.logger.error(f"Outer error in _process_wiki_queue for query '{query}' (user {original_message_obj.author.id}): {e}", exc_info=True)
            try:
                await commons.send_long_message(original_message_obj, f"{original_message_obj.author.mention}, a critical error occurred while handling your queued wiki request for '{query}'.")
            except Exception:
                pass
        finally:
            self.is_wiki_search_active = False
            if self.wiki_search_queue:
                self.logger.debug(f"Wiki queue has {len(self.wiki_search_queue)} items. Scheduling next processing.")
                asyncio.create_task(self._process_wiki_queue())
            else:
                self.logger.debug("Wiki queue is empty. Not scheduling further processing.")

    async def handle_wiki_search_request(self, message: disnake.Message, query: str):
        if self.is_wiki_search_active or self.wiki_search_queue:
            self.wiki_search_queue.append({'message': message, 'query': query})
            queue_position = len(self.wiki_search_queue)
            await database.log_wiki_search_event(user_id=message.author.id, query_text=query, event_type='queued', queue_length=queue_position)
            feedback = f"{message.author.mention}, your request for '{query}' has been added to the queue. "
            if self.is_wiki_search_active and self._current_active_query:
                 feedback += f"I am currently processing a request for '{self._current_active_query}'. "
            feedback += f"You are at position {queue_position} in the queue ({len(self.wiki_search_queue)} total)."
            try:
                await message.channel.send(feedback)
            except disnake.HTTPException:
                self.logger.warning("Failed to send queue feedback message.")
            if not self.is_wiki_search_active:
                self.logger.info("Triggering queue processing as a new item was added and nothing is active.")
                asyncio.create_task(self._process_wiki_queue())
        else:
            self.logger.info(f"Processing wiki search immediately for '{query}' from user {message.author.id}. No queue.")
            await database.log_wiki_search_event(user_id=message.author.id, query_text=query, event_type='processing_started_immediate', queue_length=0)
            self.is_wiki_search_active = True
            try:
                await self._execute_search_and_send(message, query)
            finally:
                self.is_wiki_search_active = False
                if self.wiki_search_queue:
                    self.logger.info("Immediate search finished. Triggering queue processing for items added concurrently.")
                    asyncio.create_task(self._process_wiki_queue())

def setup(bot):
    bot.add_cog(LLMCog(bot)) 