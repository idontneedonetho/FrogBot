# modules.llm.utils.tools

from google import genai
import logging
from typing import Optional, Any, TYPE_CHECKING, Callable, Coroutine, Dict
from modules.llm.utils.config import DEFAULT_HISTORY_MESSAGES, MAX_HISTORY_REQUEST

if TYPE_CHECKING:
    from ..llm import LLMCog 
    import disnake 

logger = logging.getLogger(__name__)

take_note_func = genai.types.FunctionDeclaration(
    name="take_note",
    description="Records a piece of information, correction, or important detail mentioned in the conversation for future reference. Use this when users provide new facts, correct previous statements, or highlight something significant.",
    parameters={
        "type": "object",
        "properties": {
            "note_content": {
                "type": "string",
                "description": "The specific piece of information or text to be recorded as a note."
            },
            "context": {
                "type": "string",
                "description": "Optional: Brief context about the note, like who provided the information or what message it relates to (e.g., 'Correction from UserX about parameter Y')."
            },
            "is_global": {
                "type": "boolean",
                "description": "Optional (defaults to false/channel-specific): Set to true ONLY if this note represents a general fact or preference applicable across ALL channels. Leave false/omit for channel-specific info."
            }
        },
        "required": ["note_content"]
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

update_note_func = genai.types.FunctionDeclaration(
    name="update_note",
    description="Updates an existing note identified by its ID with new content. Use this when new information significantly overlaps with or corrects an existing note retrieved from context.",
    parameters={
        "type": "object",
        "properties": {
            "note_id": {
                "type": "string",
                "description": "The unique ID of the note to be updated. Get this from the [Relevant Notes Retrieved] context."
            },
            "new_content": {
                "type": "string",
                "description": "The revised or updated content for the note."
            }
        },
        "required": ["note_id", "new_content"]
    }
)

delete_note_func = genai.types.FunctionDeclaration(
    name="delete_note",
    description="Deletes a specific note using its unique ID. Use this when a retrieved note is confirmed to be completely outdated, irrelevant, or incorrect.",
    parameters={
        "type": "object",
        "properties": {
            "note_id": {
                "type": "string",
                "description": "The unique ID of the note to be deleted. Get this from the [Relevant Notes Retrieved] context."
            }
        },
        "required": ["note_id"]
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
        take_note_func,
        update_note_func,
        delete_note_func,
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

async def _handle_take_note(cog: 'LLMCog', message: 'disnake.Message', args: Dict[str, Any]) -> genai.types.Part:
    action_name = "take_note"
    note_content = args.get("note_content")
    context = args.get("context")
    is_global = args.get("is_global", False)
    response_data = {}
    if note_content:
        await cog.save_note(
            note_content=note_content,
            context=context,
            channel_id=message.channel.id,
            is_global=is_global
        )
        response_data = {"status": "note_saved", "note_content_preview": note_content[:50]+"..." if len(note_content) > 50 else note_content}
    else:
        logger.warning("take_note call without note_content.")
        response_data = {"error": "missing note_content"}
    return genai.types.Part(
        function_response=genai.types.FunctionResponse(name=action_name, response=response_data)
    )

async def _handle_update_note(cog: 'LLMCog', message: 'disnake.Message', args: Dict[str, Any]) -> genai.types.Part:
    action_name = "update_note"
    note_id = args.get("note_id")
    new_content = args.get("new_content")
    response_data = {}
    if note_id and new_content:
        await cog.update_note_content(
            note_id=note_id,
            new_content=new_content,
            channel_id=message.channel.id
        )
        response_data = {"status": "note_updated", "note_id": note_id, "new_content_preview": new_content[:50]+"..." if len(new_content) > 50 else new_content}
    else:
        logger.warning(f"update_note call missing note_id ({note_id}) or new_content.")
        response_data = {"error": "missing note_id or new_content"}
    return genai.types.Part(
        function_response=genai.types.FunctionResponse(name=action_name, response=response_data)
    )

async def _handle_delete_note(cog: 'LLMCog', message: 'disnake.Message', args: Dict[str, Any]) -> genai.types.Part:
    action_name = "delete_note"
    note_id = args.get("note_id")
    response_data = {}
    if note_id:
        success = await cog.delete_note(note_id=note_id)
        if success:
            response_data = {"status": "note_deleted", "note_id": note_id}
        else:
            response_data = {"error": "failed to delete note or note not found", "note_id": note_id}
    else:
        logger.warning("delete_note call missing note_id.")
        response_data = {"error": "missing note_id"}
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
    history_result = await cog._get_recent_channel_history(message.channel, num_to_fetch)
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
    "take_note": _handle_take_note,
    "update_note": _handle_update_note,
    "delete_note": _handle_delete_note,
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