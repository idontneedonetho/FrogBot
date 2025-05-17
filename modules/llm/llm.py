# modules.llm.llm

from typing import List, Optional, Tuple, Any, Dict
import modules.llm.utils.tools as tool_helpers
import modules.llm.utils.config as llmconfig
from deepwiki.deepwiki import DeepWikiClient
from deepwiki.models import QueryResponse
import modules.llm.utils.utils as utils
from modules.utils import database
from modules.utils import commons
from disnake.ext import commands
from datetime import datetime
from google import genai
from core import config
from mem0 import Memory
from PIL import Image
import collections
import logging
import asyncio
import disnake
import random
import json
import time
import re
import os

logger = logging.getLogger(__name__)
logging.getLogger('disnake').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)

class LLMCog(commands.Cog):
    __slots__ = ('bot', 'genai_client', 'chat_session', 'last_message_canceled', 'message_history', 'frogpilot_wiki_client',
                 'wiki_search_queue', 'is_wiki_search_active', '_current_active_query', 'mem0_memory')

    def __init__(self, bot):
        self.bot = bot
        self.logger = logger
        self.logger.info("Initializing LLM Cog...")
        self.gemini_api_key = config.read().get('GOOGLE_API_KEY')
        if not self.gemini_api_key:
            self.logger.error("Google Gemini API key not found in config. Core LLM features (and Mem0) will likely be disabled or fail.")
        self.genai_client: Optional[genai.Client] = None
        self.chat_session: Optional[Any] = None
        self.mem0_memory: Optional[Memory] = None
        self.last_message_canceled: bool = False
        self.message_history: List[genai.types.Part] = []
        self.frogpilot_wiki_client: Optional[DeepWikiClient] = None
        self.wiki_search_queue = collections.deque()
        self.is_wiki_search_active: bool = False
        self._current_active_query: Optional[str] = None

    async def cog_load(self):
        if not self.gemini_api_key:
            self.logger.error("LLM Cog cannot load: Google Gemini API key is missing. This is required for Mem0 as well.")
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
        self.logger.info("Initializing Mem0 Memory Layer...")
        try:
            if self.gemini_api_key:
                mem0_llm_config = {
                    "provider": "openai",
                    "config": {
                        "api_key": self.gemini_api_key,
                        "model": "gemini-2.0-flash",
                        "openai_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                    }
                }
                mem0_embedder_config = {
                    "provider": "openai",
                    "config": {
                        "api_key": self.gemini_api_key,
                        "model": "gemini-embedding-exp-03-07",
                        "openai_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", 
                    }
                }
                qdrant_storage_path = "data/mem0_qdrant_storage"
                os.makedirs(qdrant_storage_path, exist_ok=True)
                self.logger.info(f"Ensuring Qdrant storage directory exists at: {os.path.abspath(qdrant_storage_path)}")
                mem0_vector_store_config = {
                    "provider": "qdrant",
                    "config": {
                        "path": qdrant_storage_path,
                        "on_disk": True,
                    }
                }
                mem0_config = {
                    "llm": mem0_llm_config,
                    "embedder": mem0_embedder_config,
                    "vector_store": mem0_vector_store_config
                }
                self.mem0_memory = Memory.from_config(config_dict=mem0_config)
                self.logger.info("Mem0 Memory Layer initialized successfully using Google Gemini (via OpenAI-compatible endpoint with dict config).")
            else:
                self.logger.error("Mem0 could not be initialized: Google Gemini API key was not available after the initial check.")
                self.mem0_memory = None
        except Exception as e:
            self.logger.error(f"Failed to initialize Mem0 Memory Layer: {e}", exc_info=True)
            self.mem0_memory = None
        if not self.mem0_memory:
            self.logger.warning("Mem0 Memory Layer failed to initialize. Note-related features will be significantly impacted or disabled.")
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
                    tools=[tool_helpers.all_tools]
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
            self.logger.debug(f"Processing message {message.id}...")
            timeout = llmconfig.VIDEO_TIMEOUT if has_video else llmconfig.DEFAULT_TIMEOUT
            current_turn_content = []
            if self.message_history:
                current_turn_content.extend(self.message_history)
            current_turn_content.extend(contents)
            if len(current_turn_content) > llmconfig.MAX_MESSAGE_HISTORY_PARTS:
                self.message_history = current_turn_content[-llmconfig.MAX_MESSAGE_HISTORY_PARTS:]
                self.logger.debug(f"Trimmed combined message history to last {llmconfig.MAX_MESSAGE_HISTORY_PARTS} parts for this turn")
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
                self.logger.debug(f"Gemini API Response received for MSG ID {message.id}. Analyzing structure...")
                try:
                    if api_response.candidates:
                        self.logger.debug(f"  API RSP Candidates: {len(api_response.candidates)} for MSG ID {message.id}")
                        for idx, cand in enumerate(api_response.candidates):
                            self.logger.debug(f"    API RSP Candidate {idx+1} for MSG ID {message.id}:")
                            safety_ratings_str = "N/A"
                            if hasattr(cand, 'safety_ratings') and cand.safety_ratings:
                                 safety_ratings_str = str([(sr.category.name, sr.probability.name) for sr in cand.safety_ratings])
                            self.logger.debug(f"      Safety Ratings: {safety_ratings_str} for MSG ID {message.id}")
                            finish_reason_str = "N/A"
                            if hasattr(cand, 'finish_reason') and cand.finish_reason is not None:
                                finish_reason_str = f"{cand.finish_reason.name} (Value: {cand.finish_reason.value})"
                            self.logger.debug(f"      Finish Reason: {finish_reason_str} for MSG ID {message.id}")
                    else:
                        self.logger.debug(f"  API RSP Candidates list: Empty or None for MSG ID {message.id}.")
                    prompt_feedback_block_reason_str = "N/A"
                    prompt_feedback_safety_ratings_str = "N/A"
                    if hasattr(api_response, 'prompt_feedback') and api_response.prompt_feedback:
                        if api_response.prompt_feedback.block_reason:
                            prompt_feedback_block_reason_str = str(api_response.prompt_feedback.block_reason.name)
                        if api_response.prompt_feedback.safety_ratings:
                            prompt_feedback_safety_ratings_str = str([(sr.category.name, sr.probability.name) for sr in api_response.prompt_feedback.safety_ratings])
                    self.logger.debug(f"  Prompt Feedback: BlockReason='{prompt_feedback_block_reason_str}', SafetyRatings='{prompt_feedback_safety_ratings_str}' for MSG ID {message.id}")
                except Exception as log_ex:
                    self.logger.error(f"Error during detailed logging of API response for MSG ID {message.id}: {log_ex}", exc_info=True)
            else:
                self.logger.warning(f"Gemini API Response object was None for MSG ID {message.id}")
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

    async def _get_memory_context(self, query: str, user_id: str, channel_id: Optional[str] = None) -> str:
        self.logger.info(f"ENTERED _get_memory_context for user {user_id} in channel {channel_id}.")
        memory_context = ""
        if not self.mem0_memory:
            self.logger.warning("Mem0 Memory Layer not available. Cannot retrieve memories.")
            return memory_context
        try:
            search_query = query
            if channel_id:
                if query:
                    search_query = f"Context: channel {channel_id}. Query: {query}"
            self.logger.debug(f"Attempting to retrieve memories for user {user_id} with final search_query: '{search_query}'")
            retrieved_memories = self.mem0_memory.search(query=search_query, user_id=user_id, limit=llmconfig.MAX_NOTES)
            self.logger.debug(f"Raw retrieved_memories from mem0.search for user {user_id}: {retrieved_memories}")
            if retrieved_memories and isinstance(retrieved_memories, dict) and retrieved_memories.get("results"):
                memory_lines = []
                for i, entry in enumerate(retrieved_memories["results"]):
                    memory_id = entry.get('id', 'N/A')
                    score = entry.get('score', 'N/A')
                    timestamp = entry.get('timestamp', 'N/A')
                    text = entry.get('memory', '')
                    metadata = entry.get('metadata', {})
                    mem_channel_id = metadata.get('channel_id', 'N/A')
                    is_global_mem = metadata.get('is_global', False)
                    try:
                        score_float = float(score)
                        score_str = f"{score_float:.4f}"
                    except (ValueError, TypeError):
                        score_str = str(score)

                    memory_lines.append(
                        f"[{i+1}] ID={memory_id} Score={score_str} (Taken {timestamp}, "
                        f"Channel: {mem_channel_id}, Global: {is_global_mem}): {text}"
                    )
                if memory_lines:
                    memory_context = f"[Retrieved Memories (mem0):]\\n" + "\n".join(memory_lines)
                    self.logger.debug(f"Formatted {len(retrieved_memories['results'])} memories from mem0 for user {user_id}.")
                else:
                    self.logger.debug(f"No processable 'results' in retrieved_memories for user {user_id}, or results were empty.")
            else:
                self.logger.debug(f"mem0.search did not return a dict with a 'results' list for user {user_id}. Response: {retrieved_memories}")
        except Exception as e:
            self.logger.error(f"Error retrieving memories from Mem0 for user {user_id}, query '{query}': {e}", exc_info=True)
        return memory_context

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
            max_shown_queries = llmconfig.MAX_WIKI_STATUS_QUERIES_DISPLAYED
            display_queries = ongoing_searches_for_prompt[:max_shown_queries]
            search_list_str = [f"'{q}'" for q in display_queries]
            status_parts = []
            if self.is_wiki_search_active and self._current_active_query:
                status_parts.append(f"Currently processing: '{self._current_active_query}'")
            if self.wiki_search_queue:
                status_parts.append(f"{len(self.wiki_search_queue)} in queue")
            status_line = " (".join(status_parts) + ")" if status_parts else ""
            base_search_str = f"[FrogPilot Wiki Status {status_line}: Queries include {', '.join(search_list_str)}]"
            if len(ongoing_searches_for_prompt) > max_shown_queries:
                ongoing_searches_str = base_search_str + f" and {len(ongoing_searches_for_prompt) - max_shown_queries} more..."
            else:
                ongoing_searches_str = base_search_str
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
                        self.logger.debug(f"Processed video URL: {url}")
                    else:
                        self.logger.debug(f"Processed file URL: {url}")
                elif isinstance(media_part, Image.Image):
                    self.logger.debug(f"Processed image URL: {url}")
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
                self.logger.debug(f"Processed attachment: {attachment.filename}")
        return media_parts, has_video

    async def process_media_content(self, message: disnake.Message) -> Tuple[List[Any], bool]:
        initial_contents = []
        prompt_parts = []
        prompt_parts.append(llmconfig.get_formatted_system_prompt(self.bot.user.display_name))
        user_id_str = str(message.author.id)
        channel_id_str = str(message.channel.id)
        memory_context_str = await self._get_memory_context(message.content or "", user_id=user_id_str, channel_id=channel_id_str)
        if memory_context_str:
            prompt_parts.append(memory_context_str)
        wiki_status = self._get_wiki_status_context()
        if wiki_status:
            prompt_parts.append(wiki_status)
        reply_context = await utils.build_reply_chain_context(message, self.bot)
        if reply_context:
            prompt_parts.append(reply_context)
        forward_context = utils.extract_forwarded_content(message)
        if forward_context:
            prompt_parts.append(forward_context)
        formatted_current_msg = utils.format_discord_message(message, self.bot)
        prompt_parts.append(f"[Current Message:]\n{json.dumps(formatted_current_msg, indent=2)}")
        full_prompt_str = "\n".join(filter(None, prompt_parts))
        initial_contents.append(full_prompt_str)
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
        self.logger.debug(f"Executing final action: {final_action_name} with args: {dict(final_action_args)}")
        try:
            if final_action_name == "send_message":
                content = final_action_args.get("content", "").strip()
                reply_to_original = final_action_args.get("reply_to_original", False)
                if not content:
                    self.logger.warning("send_message call with empty content. Treating as effectively ignored.")
                    return True, None
                should_send = await self.simulate_typing_and_check_intervention(message, content)
                if should_send:
                    self.logger.debug(f"Intervention check passed for {message.id}. Sending message.")
                    content_converted = await utils.convert_mentions(content, message)
                    await commons.send_long_message(message, content_converted, reply_to_original)
                    return True, None
                else:
                    self.logger.debug(f"Intervention check failed for {message.id}. Preparing cancellation feedback for LLM.")
                    cancellation_feedback = genai.types.Part(
                        function_response=genai.types.FunctionResponse(
                            name=final_action_name,
                            response={"status": "cancelled_due_to_intervention",
                                      "reason": "A subsequent message likely made the planned response irrelevant or user cancelled."}
                        )
                    )
                    return False, [cancellation_feedback]
            elif final_action_name == "ignore_message":
                self.logger.debug("Executing final ignore_message action.")
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

    def _classify_llm_parts(self, parts_from_llm: List[genai.types.Part]) -> Tuple[List[genai.types.FunctionCall], Optional[genai.types.FunctionCall], List[str]]:
        intermediate_tool_calls = []
        potential_final_action_call = None
        text_parts = []
        for part in parts_from_llm:
            if part.function_call:
                action_name = part.function_call.name
                if action_name in ["send_message", "ignore_message"]:
                    if not potential_final_action_call:
                        potential_final_action_call = part.function_call
                        self.logger.debug(f"Identified potential final action: {action_name}")
                    else:
                        self.logger.warning(f"Multiple final actions ({potential_final_action_call.name}, then {action_name}) proposed by LLM in one turn. Using the first: {potential_final_action_call.name}.")
                else:
                    intermediate_tool_calls.append(part.function_call)
                    self.logger.debug(f"Identified intermediate tool call: {action_name}")
            elif hasattr(part, 'text') and part.text:
                text_parts.append(part.text)
        return intermediate_tool_calls, potential_final_action_call, text_parts

    async def _process_intermediate_tool_calls(self, tool_calls: List[genai.types.FunctionCall], message: disnake.Message) -> List[genai.types.Part]:
        responses_to_send_to_llm = []
        if not tool_calls:
            return responses_to_send_to_llm
        self.logger.debug(f"Processing {len(tool_calls)} intermediate tool call(s)...")
        for func_call in tool_calls:
            tool_action_name = func_call.name
            self.logger.debug(f"Executing intermediate tool: {tool_action_name} with args: {dict(func_call.args)}")
            try:
                response_part_from_tool = await tool_helpers.process_intermediate_tool_call(self, message, func_call)
                if response_part_from_tool:
                    responses_to_send_to_llm.append(response_part_from_tool)
            except Exception as e:
                self.logger.error(f"Critical error during intermediate tool processing '{tool_action_name}': {e}", exc_info=True)
                responses_to_send_to_llm.append(genai.types.Part(
                    function_response=genai.types.FunctionResponse(
                        name=tool_action_name,
                        response={"error": f"Critical failure processing tool: {e}"}
                    )
                ))
        self.logger.debug(f"Collected {len(responses_to_send_to_llm)} response part(s) from intermediate tools.")
        return responses_to_send_to_llm

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
        while loop_iterations < llmconfig.MAX_LLM_RESPONSE_LOOPS:
            loop_iterations += 1
            self.logger.debug(f"LLM response processing loop: Iteration {loop_iterations}/{llmconfig.MAX_LLM_RESPONSE_LOOPS}")
            if not parts_to_process_from_llm and loop_iterations > 1:
                self.logger.debug("No more parts from LLM to process in this iteration.")
                break
            intermediate_tool_calls, potential_final_action_call, current_llm_response_text_parts = self._classify_llm_parts(parts_to_process_from_llm)
            parts_to_process_from_llm = []
            if intermediate_tool_calls:
                tool_responses_for_llm = await self._process_intermediate_tool_calls(intermediate_tool_calls, message)
                if tool_responses_for_llm:
                    self.logger.debug(f"Sending {len(tool_responses_for_llm)} intermediate function result(s) back to the model.")
                    try:
                        follow_up_response = await self.generate_content_with_timeout(
                            message=message,
                            chat_session=self.chat_session,
                            contents=tool_responses_for_llm,
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
                else:
                    self.logger.info("Intermediate tool(s) were processed but returned no data for the LLM. Checking for final action from original LLM response.")
            if potential_final_action_call:
                action_completed_this_step, feedback_parts_for_llm_after_final_action = await self._execute_final_action(message, potential_final_action_call)
                if feedback_parts_for_llm_after_final_action:
                    self.logger.debug("Final action (send_message) was cancelled by intervention. Sending feedback to LLM.")
                    try:
                        intervention_response = await self.generate_content_with_timeout(
                            message=message,
                            chat_session=self.chat_session,
                            contents=feedback_parts_for_llm_after_final_action,
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
                    self.logger.warning("Final action processing indicated completion or an issue handled within _execute_final_action. Breaking loop.")
                    final_action_has_executed_this_turn = True
                    break
            elif current_llm_response_text_parts:
                final_text = "".join(current_llm_response_text_parts).strip()
                if final_text:
                    self.logger.warning(f"Model returned plain text instead of a function call after {loop_iterations-1} tool iteration(s): '{final_text[:200]}...'")
                break
            else:
                self.logger.debug("LLM response had no actionable function calls or text for this iteration.")
                break 
        if not final_action_has_executed_this_turn:
            self.logger.warning(f"LLM processing for message {message.id} completed after {loop_iterations} iteration(s) without an explicit final action (send/ignore) being successfully executed or intervention handled. Defaulting to ignore.")

    async def _perform_intervention_llm_check(self, 
                                              original_message: disnake.Message, 
                                              planned_content: str, 
                                              trigger_message: disnake.Message) -> bool:
        self.logger.debug(f"Performing intervention LLM check. Planned: '{planned_content[:50]}...'. Trigger by {trigger_message.author.display_name}: '{trigger_message.content[:50]}...'")
        formatted_trigger_msg = utils.format_discord_message(trigger_message, self.bot)
        history_context_str = ""
        num_history_to_fetch = llmconfig.HISTORY_TURNS_FOR_CHECK * 2 + 1
        try:
            history_messages_raw = []
            async for hist_msg in original_message.channel.history(limit=num_history_to_fetch, before=trigger_message):
                history_messages_raw.append(hist_msg)
            formatted_history_lines = []
            for item in reversed(history_messages_raw):
                formatted_item = utils.format_discord_message(item, self.bot)
                author = formatted_item.get('author', 'Unknown')
                content = formatted_item.get('content', '').strip()
                if content:
                    formatted_history_lines.append(f"{author}: {content}") 
            if formatted_history_lines:
                history_context_str = "Recent Channel History (oldest first, leading up to MESSAGE_B):\n" + "\n".join(formatted_history_lines) + "\n\n---\n\n"
                self.logger.debug(f"Added {len(formatted_history_lines)} history messages to intervention check prompt.")
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
            tools=[tool_helpers.intervention_check_tool]
        )
        if not self.genai_client:
            self.logger.error("GenAI client not available for intervention LLM check. Defaulting to not sending.")
            return False
        temp_chat_for_check = self.genai_client.chats.create(
            model=llmconfig.CHAT_MODEL_NAME,
            config=intervention_config
        )
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
                    self.logger.debug("Intervention LLM check decided: SEND planned message.")
                    break
                elif func_call.name == "ignore_message":
                    should_send_planned_message = False
                    self.logger.debug("Intervention LLM check decided: IGNORE (cancel) planned message.")
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
                sleep_duration = min(llmconfig.TYPING_INTERVENTION_CHECK_INTERVAL, typing_time - elapsed_time)
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
                    async for new_msg in message.channel.history(limit=llmconfig.TYPING_INTERVENTION_HISTORY_CHECK_LIMIT, after=message, oldest_first=False):
                        if new_msg.author == self.bot.user: continue
                        self.logger.debug(f"Intervention check triggered by new message {new_msg.id} from {new_msg.author.display_name} during typing for original message {message.id}.")
                        should_send_planned_message = await self._perform_intervention_llm_check(
                            original_message=message, 
                            planned_content=content_to_send, 
                            trigger_message=new_msg
                        )
                        if not should_send_planned_message:
                            self.logger.debug(f"Intervention check determined to CANCEL planned response for original message {message.id} due to trigger message {new_msg.id}.")
                            self.last_message_canceled = True
                            return False
                        else:
                            self.logger.debug(f"Intervention check passed for trigger {new_msg.id}. Continuing typing simulation for original message {message.id}.")
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

    async def save_note(self, user_id: str, note_content: str, context: Optional[str] = None, channel_id: Optional[str] = None, is_global: bool = False):
        if not self.mem0_memory:
            self.logger.warning("Mem0 Memory Layer not available. Skipping saving note.")
            return None
        try:
            data_to_add = f"{note_content}"
            if context:
                data_to_add = f"{context}: {note_content}"
            metadata = {
                "original_context": context or "",
                "timestamp": datetime.now().isoformat(),
                "is_global": is_global,
                "source_system": "FrogBot_save_note"
            }
            if not is_global and channel_id:
                metadata['channel_id'] = str(channel_id)
            result = self.mem0_memory.add(
                data_to_add,
                user_id=user_id,
                metadata=metadata
            )
            memory_id = result.get('id', 'N/A') if isinstance(result, dict) else 'N/A (check mem0 docs for return type)'
            scope = "Global" if is_global else f"Channel {channel_id or 'N/A'}"
            log_message = f"Note Saved to Mem0 (User: {user_id}, MemID: {memory_id}, Scope: {scope}): {note_content}"
            if context:
                log_message += f" (Context: {context})"
            self.logger.debug(log_message)
            return memory_id
        except Exception as e:
            self.logger.error(f"Failed to save note to Mem0 (User: {user_id}): {e}", exc_info=True)
            return None

    async def commit_messages_to_memory(self, user_id: str, reason_to_remember: str, messages_to_commit: List[Dict[str, str]], is_global: bool = False, channel_id: Optional[str] = None):
        if not self.mem0_memory:
            self.logger.warning("Mem0 Memory Layer not available. Skipping committing messages to memory.")
            return None
        try:
            metadata = {
                "reason_provided_by_llm": reason_to_remember,
                "timestamp": datetime.now().isoformat(),
                "is_global": is_global,
                "source_system": "FrogBot_commit_messages"
            }
            if not is_global and channel_id:
                metadata['channel_id'] = str(channel_id)
            result = self.mem0_memory.add(
                messages_to_commit,
                user_id=user_id,
                metadata=metadata
            )
            memory_id_or_ids = "N/A (check mem0 result)"
            if isinstance(result, dict):
                if 'id' in result:
                    memory_id_or_ids = result['id']
                elif 'ids' in result:
                    memory_id_or_ids = result['ids']
                elif result.get('results') and isinstance(result['results'], list):
                    memory_id_or_ids = [res.get('id') for res in result['results'] if isinstance(res, dict) and 'id' in res]
            scope = "Global" if is_global else f"Channel {channel_id or 'N/A'}"
            log_message = f"Committed context to Mem0 (User: {user_id}, MemID(s): {memory_id_or_ids}, Scope: {scope}): Reason: {reason_to_remember}, with {len(messages_to_commit)} messages."
            self.logger.debug(log_message)
            return memory_id_or_ids
        except Exception as e:
            self.logger.error(f"Failed to commit messages to Mem0 (User: {user_id}): {e}", exc_info=True)
            return None

    async def update_note_content(self, user_id: str, memory_id: str, new_content: str, context: Optional[str] = None, channel_id: Optional[str] = None):
        if not self.mem0_memory:
            self.logger.warning(f"Mem0 Memory Layer not available. Skipping update for mem_id {memory_id}, user {user_id}.")
            return False
        try:
            updated_metadata = {
                "original_context": context or "",
                "timestamp": datetime.now().isoformat(),
            }
            if channel_id:
                 updated_metadata['channel_id'] = str(channel_id)
            self.mem0_memory.update(memory_id=memory_id, data=new_content, user_id=user_id)
            self.logger.debug(f"Note Updated in Mem0 (User: {user_id}, MemID: {memory_id}, Channel: {channel_id or 'N/A'}): {new_content}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to update note in Mem0 (User: {user_id}, MemID: {memory_id}): {e}", exc_info=True)
            return False


    async def delete_note(self, user_id: str, memory_id: str) -> bool:
        if not self.mem0_memory:
            self.logger.warning(f"Mem0 Memory Layer not available. Skipping delete for mem_id {memory_id}, user {user_id}.")
            return False
        try:
            self.mem0_memory.delete(memory_id=memory_id, user_id=user_id)
            self.logger.debug(f"Note Deleted from Mem0 (User: {user_id}, MemID: {memory_id})")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete note from Mem0 (User: {user_id}, MemID: {memory_id}): {e}", exc_info=True)
            return False

    def cog_unload(self):
        self.logger.info("LLM Cog unloading...")
        if self.frogpilot_wiki_client and hasattr(self.frogpilot_wiki_client, 'close'):
             asyncio.create_task(self.frogpilot_wiki_client.close())
        self.logger.info("LLM Cog unloading complete.")

    def _format_wiki_response_message(self, original_query: str, response: Optional[QueryResponse], author_mention: str, author_id: int) -> str:
        if not response:
            self.logger.warning(f"FrogPilot Wiki search for '{original_query}' for user {author_id} returned no response object (it was None).")
            return f"{author_mention}, sorry, the FrogPilot Wiki search for '{original_query}' didn't return any results. There might have been an issue with the search service."
        base_message = f"{author_mention}, here are the FrogPilot Wiki results for your query:\n> {original_query}\n\n"
        formatted_content_from_wiki = self.frogpilot_wiki_client.format_query_response(
            query_response=response,
            display_raw=False,
            display_filtered=True,
            filter_show_text=True,
            filter_show_markers=False,
            filter_show_newlines=False,
            display_references=True,
            display_query_id=False,
            display_query_url=False
        )
        if formatted_content_from_wiki:
            full_message = base_message + formatted_content_from_wiki.strip()
            self.logger.debug(f"Successfully formatted wiki response for '{original_query}' using deepwiki for content and references.")
            return full_message.strip()
        else:
            if response.raw_answer:
                self.logger.warning(f"deepwiki.format_query_response returned empty for '{original_query}', but raw_answer exists. Using raw_answer.")
                return f"{base_message}**Details from Wiki:**\n{response.raw_answer[:1500]}...".strip()
            self.logger.warning(f"FrogPilot Wiki search for '{original_query}' for user {author_id} completed but yielded no usable formatted content from deepwiki client.")
            return f"{base_message}The search completed, but I couldn't extract specific details for your query at this time.".strip()

    async def _execute_search_and_send(self, original_message: disnake.Message, query: str):
        author_mention = original_message.author.mention
        author_id = original_message.author.id
        channel = original_message.channel
        self._current_active_query = query
        self.logger.debug(f"Executing FrogPilot Wiki search for query: '{query}' for user {author_id}")
        feedback_msg_content = f"{author_mention}, I'm now processing your request and searching the FrogPilot Wiki for:\n> {query}\nThis will take a while... I'll ping you with the results when I'm done."
        try:
            await channel.send(feedback_msg_content)
        except disnake.HTTPException as discord_err:
            self.logger.error(f"Failed to send FrogPilot Wiki processing message: {discord_err}")
        except Exception as e:
            self.logger.error(f"Unexpected error sending FrogPilot Wiki processing message: {e}", exc_info=True)
        wiki_response: Optional[QueryResponse] = None
        final_message_to_send = ""
        try:
            if not self.frogpilot_wiki_client:
                self.logger.error(f"FrogPilot Wiki client not initialized before execution for query '{query}'.")
                final_message_to_send = f"{author_mention}, I can't search the wiki right now because the knowledge base isn't available."
            else:
                loop = asyncio.get_running_loop()
                wiki_response = await loop.run_in_executor(
                    None,
                    self.frogpilot_wiki_client.query,
                    query,
                    "" 
                )
                final_message_to_send = self._format_wiki_response_message(query, wiki_response, author_mention, author_id)
            await commons.send_long_message(original_message, final_message_to_send)
            await database.log_wiki_search_event(user_id=author_id, query_text=query, event_type='finished_success', queue_length=len(self.wiki_search_queue))
        except Exception as dw_err:
            self.logger.error(f"Error during _execute_search_and_send for query '{query}' (user {author_id}): {dw_err}", exc_info=True)
            await database.log_wiki_search_event(user_id=author_id, query_text=query, event_type='finished_error', queue_length=len(self.wiki_search_queue), details=str(dw_err))
            error_message = f"{author_mention}, sorry, an unexpected error occurred while I was working on your wiki search for '{query}'."
            try:
                await commons.send_long_message(original_message, error_message)
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
        self.logger.debug(f"Dequeued wiki search for '{query}' from user {original_message_obj.author.id}. Queue length now: {len(self.wiki_search_queue)}")
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
                self.logger.debug("Triggering queue processing as a new item was added and nothing is active.")
                asyncio.create_task(self._process_wiki_queue())
        else:
            self.logger.debug(f"Processing wiki search immediately for '{query}' from user {message.author.id}. No queue.")
            await database.log_wiki_search_event(user_id=message.author.id, query_text=query, event_type='processing_started_immediate', queue_length=0)
            self.is_wiki_search_active = True
            try:
                await self._execute_search_and_send(message, query)
            finally:
                self.is_wiki_search_active = False
                if self.wiki_search_queue:
                    self.logger.debug("Immediate search finished. Triggering queue processing for items added concurrently.")
                    asyncio.create_task(self._process_wiki_queue())

def setup(bot):
    bot.add_cog(LLMCog(bot)) 