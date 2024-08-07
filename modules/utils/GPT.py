# modules.utils.GPT

from llama_index.core.tools import QueryEngineTool, ToolMetadata, FunctionTool
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.tools.duckduckgo import DuckDuckGoSearchToolSpec
from llama_index.vector_stores.duckdb import DuckDBVectorStore
from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.llms import MessageRole as Role
from modules.utils.commons import send_long_message
from llama_index.agent.openai import OpenAIAgent
from llama_index.core.llms import ChatMessage
from llama_index.llms.openai import OpenAI
from disnake.ext import commands
from dotenv import load_dotenv
import traceback
import asyncio
import disnake
import openai
import os

class HistoryChatMessage:
    def __init__(self, content, role, user_name=None, additional_kwargs=None):
        self.content = content
        self.role = role
        self.user_name = user_name
        self.additional_kwargs = additional_kwargs if additional_kwargs else {}

async def fetch_reply_chain(message, max_tokens=4096):
    context, tokens_used = [], 0
    remaining_tokens = max_tokens - len(message.content) // 4
    while message.reference and tokens_used < remaining_tokens:
        try:
            message = await message.channel.fetch_message(message.reference.message_id)
            role = Role.ASSISTANT if message.author.bot else Role.USER
            message_tokens = len(message.content) // 4
            if tokens_used + message_tokens > remaining_tokens:
                break  
            context.append(HistoryChatMessage(f"{message.content}\n", role, message.author.name if not message.author.bot else None))
            tokens_used += message_tokens
        except Exception as e:
            print(f"Error fetching reply chain message: {e}")
            break
    return context[::-1]

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')
Settings.llm = OpenAI(model="gpt-4o-mini", max_tokens=1000)
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5", device="cpu")

search_spec = DuckDuckGoSearchToolSpec()
def site_search(input, site):
    query = input if isinstance(input, str) else input.get('query')
    return search_spec.duckduckgo_full_search(query=f"{query} site:{site}")

sites = ["comma.ai", "oneclone.net", "springerelectronics.com", "shop.retropilot.org"]
s_tools = {
    site: FunctionTool.from_defaults(
        fn=lambda input, site=site: site_search(input, site),
        tool_metadata=ToolMetadata(
            name=f"{site.replace('.', '_')}_Search_Tool",
            description=f"A tool that can be used to search {site} for OpenPilot related products."
        )
    ) for site in sites
}

def create_query_engine(collection_name, tool_name, description):
    vector_store = DuckDBVectorStore(database_name=f"{collection_name}.duckdb", embed_dim=384, persist_dir="./db_files/")
    index = VectorStoreIndex.from_vector_store(vector_store)
    engine = index.as_query_engine()
    tool = QueryEngineTool(
        query_engine=engine,
        metadata=ToolMetadata(
            name=tool_name,
            description=description,
        ),
    )
    return tool

collections = {
    "commaai_openpilot": {
        "tool_name": "OpenPilot_code",
        "description": "This collection contains the complete source code for OpenPilot, an open-source driving agent that performs the functions of Adaptive Cruise Control (ACC) and Lane Keeping Assist System (LKAS) for various car models."
    },
    "twilsonco_openpilot": {
        "tool_name": "NNFF_Tool",
        "description": "This tool provides an in-depth explanation and analysis of the Neural Network FeedForward (NNFF) mechanism used in OpenPilot. It includes detailed documentation and examples to help understand how NNFF is implemented and utilized in the OpenPilot system. More details can be found at: https://github.com/twilsonco/openpilot/tree/log-info"
    },
    "commit": {
        "tool_name": "commit_data",
        "description": "This collection contains the commit history of the FrogPilot codebase. It provides detailed information about each commit, including changes made, authorship, and timestamps, allowing for comprehensive tracking of the project's development over time."
    },
    "wiki": {
        "tool_name": "Wiki_Tool",
        "description": "This is the main wiki for FrogPilot, containing extensive data and documentation such as settings, configuration guides, and usage instructions. This data is a work in progress (WIP) and is continuously updated to provide the most accurate and helpful information for users."
    },
}

query_engine_tools = [create_query_engine(name, data["tool_name"], data["description"]) for name, data in collections.items()]
query_engine_tools.extend(s_tools.values())

async def process_message_with_llm(message, client):
    content = message.content.replace(client.user.mention, '').strip()
    if not content:
        return
    try:
        async with message.channel.typing():
            reply_chain = await fetch_reply_chain(message)
            chat_history = [ChatMessage(content=msg.content, role=msg.role, user_name=msg.user_name) for msg in reply_chain]
            channel_prompts = {
                'bug-reports': (
                    "Assist with bug reports. Request: issue details, Route ID, installed branch name, software update status, car details. "
                    "Compile a report for the user to edit and post in #bug-reports. Remind them to backup their settings. "
                    "Remember, comma connect routes must be accessed from the `https://connect.comma.ai` website. "
                    "Routes are stored on the front page of connect."
                ),
                'default': (
                    "Provide accurate responses using server and channel names. "
                    "Give context and related information. Use available tools. "
                    "Maintain respectfulness. If an unknown acronym is encountered, use Wiki_Tool to find its meaning and then perform another search with the newly found information. "
                    "Provide source links. Use multiple tools for comprehensive responses."
                )
            }
            system_prompt = (
                f"You are '{client.user}', assisting '{message.author}' in the '{message.channel}' of the '{message.guild}' server. "
                "Keep all information relevant to this server and context. Provide accurate support as an OpenPilot community assistant. "
                "Respond appropriately to the conversation context. Avoid giving code interaction instructions unless specifically asked. "
                "Examine code for answers when necessary. Use the provided tools to give comprehensive responses and maintain respectfulness throughout the interaction."
            )
            if getattr(message.channel, 'parent_id', None) == 1162100167110053888:
                system_prompt += channel_prompts['bug-reports']
            else:
                system_prompt += channel_prompts['default']
            chat_engine = OpenAIAgent.from_tools(query_engine_tools, system_prompt=system_prompt, verbose=True, chat_history=chat_history)
            chat_history.append(ChatMessage(content=content, role="user"))
            chat_response = await asyncio.to_thread(chat_engine.chat, content)

            if not chat_response or not chat_response.response:
                error_message = "There was an error processing the message." if not chat_response else "I didn't get a response."
                await message.channel.send(error_message)
                return

            chat_history.append(ChatMessage(content=chat_response.response, role="assistant"))
            response_text = [chat_response.response]

            if isinstance(message.channel, disnake.Thread):
                response_channel = message.channel
            else:
                response_channel = await message.create_thread(name=f"FrogBot Conversation: {content[:50]}...")
                if not reply_chain:
                    response_text.append(f"\n*Continue the conversation in this thread to maintain context.*")

            await send_long_message(response_channel, '\n'.join(response_text))

    except Exception as e:
        await message.channel.send(f"An error occurred: {str(e)}")

class OpenPilotAssistant(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.client.user or message.author.bot:
            return
        
        if self.client.user in message.mentions:
            await process_message_with_llm(message, self.client)
        else:
            await self.client.process_commands(message)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.send("Sorry, I didn't understand that command.")
        else:
            tb_str = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            print(f'An error occurred: {error}\n{tb_str}')

def setup(client):
    client.add_cog(OpenPilotAssistant(client))
