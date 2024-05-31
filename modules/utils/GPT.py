# modules.utils.GPT

from llama_index.core.tools import QueryEngineTool, ToolMetadata, FunctionTool
from modules.utils.commons import send_long_message, fetch_reply_chain
from llama_index.core.response_synthesizers import CompactAndRefine
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.tools.duckduckgo import DuckDuckGoSearchToolSpec
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.vector_stores.postgres import PGVectorStore
from llama_index.core import Settings, VectorStoreIndex
from llama_index.agent.openai import OpenAIAgent
from llama_index.core.agent import ReActAgent
from llama_index.core.llms import ChatMessage
from llama_index.llms.openai import OpenAI
from sqlalchemy import make_url
from dotenv import load_dotenv
import asyncio
import openai
import torch
import os

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')
Settings.llm = OpenAI(model="gpt-3.5-turbo", max_tokens=1000)
# Settings.llm = OpenAI(model="gpt-4o", max_tokens=1000)
device = "cuda" if torch.cuda.is_available() else "cpu"
print("GPU available:", torch.cuda.is_available())
Settings.embed_model = HuggingFaceEmbedding(model_name="avsolatorio/NoInstruct-small-Embedding-v0", device=device)

'''POSTGRES DATABASE CREATION'''
connection_string = os.getenv('POSTGRES_CONNECTION_STRING')
db_name = "bot_vector_db"
url = make_url(connection_string)
embed_dim=384

'''GOOGLE SEARCH TOOL'''
google_search_spec = DuckDuckGoSearchToolSpec()
search_spec = DuckDuckGoSearchToolSpec()
def site_search(input, site):
    query = input if isinstance(input, str) else input.get('query')
    return search_spec.duckduckgo_full_search(query=query + " site:" + site)

sites = ["comma.ai", "oneclone.net", "springerelectronics.com", "shop.retropilot.org"]
s_tools = {}
for site in sites:
    t_name = site.replace('.', '_')
    desc = f"A tool that can be used to search {site} for OpenPilot related products."
    s_tools[site] = FunctionTool.from_defaults(
        fn=lambda input, site=site: site_search(input, site),
        tool_metadata=ToolMetadata(name=f"{t_name}_Search_Tool", description=desc)
    )

'''QUERY ENGINE TOOLS'''
def create_query_engine(collection_name, tool_name, description):
    vector_store = PGVectorStore.from_params(
        database=db_name,
        host=url.host,
        password=url.password,
        port=url.port,
        user=url.username,
        table_name=f"{collection_name}_docs",
        embed_dim=embed_dim,
        hybrid_search=True,
        text_search_config="english",
        cache_ok=True,
    )
    index = VectorStoreIndex.from_vector_store(vector_store)
    vector_retriever = index.as_retriever(
        vector_store_query_mode="default",
        similarity_top_k=5,
    )
    text_retriever = index.as_retriever(
        vector_store_query_mode="sparse",
        similarity_top_k=12,
    )
    retriever = QueryFusionRetriever(
        [vector_retriever, text_retriever],
        similarity_top_k=5,
        num_queries=1,
        mode="relative_score",
    )
    response_synthesizer = CompactAndRefine()
    tool = QueryEngineTool(
        query_engine=RetrieverQueryEngine(
            retriever=retriever,
            response_synthesizer=response_synthesizer,
        ),
        metadata=ToolMetadata(
            name=tool_name,
            description=description,
        ),
    )
    return tool

collections = {
    "discord": {"tool_name": "Discord_Tool", "description": "Data from Discord related to the OpenPilot community."},
    "FrogAi-FrogPilot": {"tool_name": "FrogPilot_Tool", "description": "This includes configuration settings and the source code for FrogPilot/OpenPilot."},
    "twilsonco-openpilot": {"tool_name": "NNFF_Tool", "description": "This provides a detailed explanation and analysis of the Neural Network FeedForward (NNFF) as used in OpenPilot. More details can be found at: https://github.com/twilsonco/openpilot/tree/log-info"},
    "commaai-openpilot-docs": {"tool_name": "OpenPilot_Docs_Tool", "description": "This is the official OpenPilot documentation. Note that it does not contain any code or information related to code settings."},
    "commaai-comma10k": {"tool_name": "Comma10k_Tool", "description": "This includes the comma10k dataset, also known as 'comma pencil', and its related information."},
    "wiki": {"tool_name": "Wiki_Tool", "description": "This contains data from the OpenPilot wiki, which includes some detailed, though not extensive, information."},
}

query_engine_tools = [create_query_engine(name, data["tool_name"], data["description"]) for name, data in collections.items()]
query_engine_tools.extend(s_tools.values())

async def process_message_with_llm(message, client):
    content = message.content.replace(client.user.mention, '').strip()
    if content:
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
                        "Maintain respectfulness. If an unknown acronym is encountered, use Discord_Tool to find its meaning and then perform another search with the newly found information. "
                        "Provide source links. Use multiple tools for comprehensive responses."
                    )
                }
                system_prompt = (
                    f"Assistant: '{client.user}'. "
                    f"Channel: '{message.channel}'. "
                    f"Server: '{message.guild}'. "
                    f"User: '{message.author}'. "
                    "Provide accurate information and support as an OpenPilot community assistant. "
                    "Respond appropriately to the conversation context. "
                    "Avoid code interaction instructions unless asked. Examine code for answers. "
                )
                bug_reports_forum_channel_id = 1162100167110053888
                if hasattr(message.channel, 'parent_id'):
                    parent_channel_id = message.channel.parent_id
                    if parent_channel_id is not None and parent_channel_id == bug_reports_forum_channel_id:
                        system_prompt += channel_prompts['bug-reports']
                    else:
                        system_prompt += channel_prompts['default']
                else:
                    system_prompt += channel_prompts['default']
                try:
                    chat_engine = OpenAIAgent.from_tools(
                        query_engine_tools,
                        system_prompt=system_prompt,
                        verbose=True,
                        chat_history=chat_history,
                    )
                except Exception as e:
                    print(f"OpenAIAgent failed with error: {str(e)}. Switching to ReActAgent.")
                    chat_engine = ReActAgent.from_tools(
                        query_engine_tools,
                        system_prompt=system_prompt,
                        verbose=True,
                        max_iterations=20,
                        chat_history=chat_history,
                    )
                chat_history.append(ChatMessage(content=content, role="user"))
                chat_response = await asyncio.to_thread(chat_engine.chat, content)
                if not chat_response or not chat_response.response:
                    await message.channel.send("There was an error processing the message." if not chat_response else "I didn't get a response.")
                    return
                chat_history.append(ChatMessage(content=chat_response.response, role="assistant"))
                response_text = [chat_response.response]
                if not reply_chain:
                    response_text.append(f"*Note: Reply directly to {client.user.mention}'s messages to maintain conversation context.*")
                response_text = '\n'.join(response_text)
                await send_long_message(message, response_text)
        except Exception as e:
            await message.channel.send(f"An error occurred: {str(e)}")
