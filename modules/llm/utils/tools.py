# modules.llm.utils.tools

from modules.llm.utils.config import DEFAULT_HISTORY_MESSAGES, MAX_HISTORY_REQUEST
from typing import Optional, Any, TYPE_CHECKING, Callable, Coroutine, Dict
import modules.llm.utils.utils as utils
from google import genai
import logging

if TYPE_CHECKING:
    from ..llm import LLMCog 
    import disnake 

logger = logging.getLogger(__name__)

remember_context_func = genai.types.FunctionDeclaration(
    name="remember_context",
    description=(
        "Processes and stores significant information, facts, user preferences, or conversational nuances from the recent dialogue. "
        "Use this to build a persistent memory about the user or topic being discussed. "
        "mem0 will infer structured memories from the provided context and messages."
    ),
    parameters={
        "type": "object",
        "properties": {
            "reason_to_remember": {
                "type": "string",
                "description": "A brief explanation or summary of what key information should be focused on or extracted from the recent messages (e.g., 'User expressed preference for sci-fi movies', 'Key decision made about project X')."
            },
            "num_recent_messages_to_include": {
                "type": "integer",
                "description": "Optional (defaults to 3): Number of recent actual messages (including user and assistant turns) to fetch from history and provide to mem0 for context and memory inference. Max typically around 5-7 to keep it focused."
            },
            "is_global": {
                "type": "boolean",
                "description": "Optional (defaults to false/user-specific): Set to true ONLY if this memory represents a general fact applicable across all contexts for this user. Leave false/omit for context-specific memories tied more to the current conversation flow."
            }
        },
        "required": ["reason_to_remember"]
    }
)

send_message_func = genai.types.FunctionDeclaration(
    name="send_message",
    description="Sends a message to the current channel. Can optionally be a direct reply to the user's original message.",
     parameters={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The text content of the message to send."
            },
            "reply_to_original": {
                "type": "boolean",
                "description": "Set to true if the message should be a direct reply to the triggering user message. Defaults to false (send as a new message)."
            }
        },
        "required": ["content"]
    }
)

react_func = genai.types.FunctionDeclaration(
    name="react_to_message",
    description="Use this to add emoji reactions to the user's message.",
     parameters={
        "type": "object",
        "properties": {
            "emoji": {
                "type": "string",
                "description": "The emoji to react with (e.g., '👍', '🤔', ':smile:')."
            }
        },
        "required": ["emoji"]
    }
)

ignore_func = genai.types.FunctionDeclaration(
    name="ignore_message",
    description="Takes no action. Use when the message doesn't require a response or reaction (e.g., off-topic chat, ambient conversation not directed at the bot)."
)

get_recent_channel_history_func = genai.types.FunctionDeclaration(
    name="get_recent_channel_history",
    description="Retrieves the most recent messages from the current channel to understand the immediate conversational context or flow, especially if the current context seems insufficient.",
    parameters={
        "type": "object",
        "properties": {
            "num_messages": {
                "type": "integer",
                "description": "Optional: The maximum number of recent messages to retrieve (e.g., 5 or 10). Defaults to 5."
            }
        }
    }
)

search_frogpilot_wiki_func = genai.types.FunctionDeclaration(
    name="search_frogpilot_wiki",
    description="Searches the FrogPilot Wiki knowledge base for information. Use this when the user asks a question about FrogPilot features, settings, or how specific functions work. Provides structured results including references.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The user's question or search query for the FrogPilot Wiki knowledge base (e.g., 'what is lane assist?', 'how does longitudinal control work?')."
            }
        },
        "required": ["query"]
    }
)

all_tools = genai.types.Tool(
    function_declarations=[
        remember_context_func,
        send_message_func,
        react_func,
        ignore_func,
        get_recent_channel_history_func,
        search_frogpilot_wiki_func
    ]
)

intervention_check_tool = genai.types.Tool(
    function_declarations=[
        send_message_func,
        ignore_func
    ]
)


async def _handle_react_to_message(cog: 'LLMCog', message: 'disnake.Message', args: Dict[str, Any]) -> Optional[genai.types.Part]:
    action_name = "react_to_message"
    emoji = args.get("emoji", "").strip('\"\' ')
    if emoji:
        try:
            await message.add_reaction(emoji)
            logger.info(f"Executed react_to_message: {emoji} for message {message.id}")
            return None
        except Exception as e:
            logger.warning(f"Failed to add reaction: {emoji} to message {message.id} - {e}")
            return genai.types.Part(
                function_response=genai.types.FunctionResponse(name=action_name, response={"error": f"Failed to add reaction: {e}", "emoji": emoji})
            )
    else:
        logger.warning("react_to_message call with empty emoji.")
        return genai.types.Part(
            function_response=genai.types.FunctionResponse(name=action_name, response={"error": "missing emoji parameter"})
        )

async def _handle_remember_context(cog: 'LLMCog', message: 'disnake.Message', args: Dict[str, Any]) -> genai.types.Part:
    action_name = "remember_context"
    reason_to_remember = args.get("reason_to_remember")
    num_messages_to_include = args.get("num_recent_messages_to_include", 3)
    is_global = args.get("is_global", False)
    user_id = str(message.author.id)
    channel_id_str = str(message.channel.id)
    response_data = {}
    if not reason_to_remember:
        logger.warning("remember_context call without reason_to_remember.")
        response_data = {"error": "missing reason_to_remember"}
        return genai.types.Part(
            function_response=genai.types.FunctionResponse(name=action_name, response=response_data)
        )
    messages_to_commit = []
    try:
        actual_num_to_fetch = max(1, num_messages_to_include)
        history_limit_for_before = max(0, actual_num_to_fetch - 1)
        fetched_discord_messages = []
        if history_limit_for_before > 0:
            async for msg in message.channel.history(limit=history_limit_for_before, before=message, oldest_first=False):
                fetched_discord_messages.append(msg)
            fetched_discord_messages.reverse()
        fetched_discord_messages.append(message)
        for msg_from_hist in fetched_discord_messages:
            role = "assistant" if msg_from_hist.author == cog.bot.user else "user"
            content = msg_from_hist.content
            if content:
                messages_to_commit.append({"role": role, "content": content})
        if not messages_to_commit:
            logger.warning("No messages found or formatted to commit to memory.")
            response_data = {"error": "no_messages_to_commit", "reason": "Could not fetch or format recent messages."}
        else:
            memory_ids = await cog.commit_messages_to_memory(
                user_id=user_id,
                reason_to_remember=reason_to_remember,
                messages_to_commit=messages_to_commit,
                is_global=is_global,
                channel_id=channel_id_str
            )
            if memory_ids:
                response_data = {
                    "status": "context_committed_to_mem0", 
                    "memory_id(s)": memory_ids,
                    "reason": reason_to_remember,
                    "num_messages_processed": len(messages_to_commit)
                }
            else:
                response_data = {"error": "failed_to_commit_context_to_mem0"}
    except Exception as e:
        logger.error(f"Error in _handle_remember_context: {e}", exc_info=True)
        response_data = {"error": f"internal_error_in_handler: {str(e)}"}
    return genai.types.Part(
        function_response=genai.types.FunctionResponse(name=action_name, response=response_data)
    )

async def _handle_get_recent_channel_history(cog: 'LLMCog', message: 'disnake.Message', args: Dict[str, Any]) -> genai.types.Part:
    action_name = "get_recent_channel_history"
    requested_num = args.get("num_messages", DEFAULT_HISTORY_MESSAGES)
    try:
        num_to_fetch = int(requested_num)
    except (ValueError, TypeError):
        logger.warning(f"Invalid num_messages '{requested_num}', using default {DEFAULT_HISTORY_MESSAGES}.")
        num_to_fetch = DEFAULT_HISTORY_MESSAGES
    num_to_fetch = max(1, min(num_to_fetch, MAX_HISTORY_REQUEST))
    logger.info(f"Executing get_recent_channel_history for {num_to_fetch} messages.")
    history_result = await utils.get_recent_channel_history(message.channel, cog.bot, num_to_fetch)
    response_data = {"history": history_result, "messages_retrieved": num_to_fetch}
    return genai.types.Part(
        function_response=genai.types.FunctionResponse(name=action_name, response=response_data)
    )

async def _handle_search_frogpilot_wiki(cog: 'LLMCog', message: 'disnake.Message', args: Dict[str, Any]) -> Optional[genai.types.Part]:
    action_name = "search_frogpilot_wiki"
    query = args.get("query")
    if not query:
        logger.warning("search_frogpilot_wiki call missing query.")
        return genai.types.Part(
            function_response=genai.types.FunctionResponse(name=action_name, response={"error": "missing query parameter"})
        )
    elif not cog.frogpilot_wiki_client:
        logger.error("FrogPilot Wiki client not initialized for search_frogpilot_wiki tool.")
        return genai.types.Part(
            function_response=genai.types.FunctionResponse(name=action_name, response={"error": "FrogPilot Wiki knowledge base is not available"})
        )
    else:
        logger.info(f"Handing off search_frogpilot_wiki with query '{query}' to LLMCog.handle_wiki_search_request")
        await cog.handle_wiki_search_request(message, query)
        return None

ToolHandlerType = Callable[['LLMCog', 'disnake.Message', Dict[str, Any]], Coroutine[Any, Any, Optional[genai.types.Part]]]
TOOL_HANDLERS: Dict[str, ToolHandlerType] = {
    "react_to_message": _handle_react_to_message,
    "remember_context": _handle_remember_context,
    "get_recent_channel_history": _handle_get_recent_channel_history,
    "search_frogpilot_wiki": _handle_search_frogpilot_wiki,
}

async def process_intermediate_tool_call(cog: 'LLMCog', message: 'disnake.Message', func_call: Any) -> Optional[genai.types.Part]:
    action_name = func_call.name
    args = func_call.args
    handler = TOOL_HANDLERS.get(action_name)
    if handler:
        try:
            return await handler(cog, message, args)
        except Exception as e:
            logger.error(f"Critical error executing tool handler for '{action_name}': {e}", exc_info=True)
            return genai.types.Part(
                function_response=genai.types.FunctionResponse(
                    name=action_name,
                    response={"error": f"Critical failure during '{action_name}' execution: {e}"}
                )
            )
    else:
        logger.warning(f"process_intermediate_tool_call received unrecognized action: {action_name}")
        return genai.types.Part(
            function_response=genai.types.FunctionResponse(
                name=action_name,
                response={"error": f"Unrecognized tool name: {action_name}"}
            )
        ) 