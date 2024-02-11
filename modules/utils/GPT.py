# GPT.py

from modules.utils.commons import send_long_message, fetch_reply_chain, fetch_message_from_link, HistoryChatMessage
from llama_index import ServiceContext, VectorStoreIndex, StorageContext
from llama_index.core.llms.types import MessageRole as Role
from llama_index.vector_stores import QdrantVectorStore
from llama_index.embeddings import OpenAIEmbedding
from llama_index.memory import ChatMemoryBuffer
from qdrant_client import QdrantClient
from llama_index.llms import Gemini, OpenAI
from dotenv import load_dotenv
import openai
import os
import re

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

try:
    client = QdrantClient(os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API'))
    vector_store = QdrantVectorStore(client=client, collection_name="openpilot-data")
    embed_model = OpenAIEmbedding(model="text-embedding-3-small")
    llm = OpenAI(model="gpt-4-turbo-preview", max_tokens=1000)
    # llm = Gemini(max_tokens=1000)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    service_context = ServiceContext.from_defaults(embed_model=embed_model, llm=llm, chunk_overlap=24, chunk_size=1024)
    index = VectorStoreIndex.from_vector_store(vector_store, service_context=service_context)
except Exception as e:
    print("Index not loaded", e)

async def process_message_with_llm(message, client):
    content = message.content.replace(client.user.mention, '').strip()
    if content:
        try:
            async with message.channel.typing():
                memory = ChatMemoryBuffer.from_defaults(token_limit=8000)
                context = await fetch_context_and_content(message, client, content)
                memory.set(context + [HistoryChatMessage(f"{message.author.name}: {content}", Role.USER)])
                chat_engine = index.as_chat_engine(
                    chat_mode="condense_plus_context",
                    memory=memory,
                    similarity_top_k=5,
                    context_prompt=(
                        f"You are {client.user.name}, an CommaAI OpenPilot-related Chat Assistant."
                        " Ensure all responses that include a table puts the table into a codeblock in the response."
                    ),
                )
                chat_response = chat_engine.chat(content)
                if not chat_response or not chat_response.response:
                    await message.channel.send("There was an error processing the message." if not chat_response else "I didn't get a response.")
                    return
                response_text = chat_response.response
                response_text = re.sub(r'^[^:]+:\s(?=[A-Z])', '', response_text)
                await send_long_message(message, response_text)
        except Exception as e:
            await message.channel.send(f"An error occurred: {str(e)}")
        
async def fetch_context_and_content(message, client, content):
    linked_message = await fetch_message_from_link(client, content) if content.startswith('https://discord.com/channels/') else message
    context = await fetch_reply_chain(linked_message)
    return context