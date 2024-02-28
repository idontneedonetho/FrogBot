# modules.utils.GPT

from modules.utils.commons import send_long_message, fetch_reply_chain, fetch_message_from_link, HistoryChatMessage
from llama_index.core import StorageContext, Settings, VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.llms import MessageRole as Role
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.llms.openai import OpenAI
from qdrant_client import QdrantClient
from dotenv import load_dotenv
import asyncio
import openai
import re
import os

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

client = QdrantClient(os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API'))
vector_store = QdrantVectorStore(client=client, collection_name="openpilot-data")
Settings.llm = OpenAI(model="gpt-4-turbo-preview", max_tokens=1000)
embed_model = OpenAIEmbedding(model="text-embedding-3-small")
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)

async def process_message_with_llm(message, client):
    content = message.content.replace(client.user.mention, '').strip()
    if content:
        try:
            async with message.channel.typing():
                memory = ChatMemoryBuffer.from_defaults(token_limit=8192)
                context = await fetch_context_and_content(message, client, content)
                memory.set(context + [HistoryChatMessage(f"{content}", Role.USER)])
                chat_engine = index.as_chat_engine(
                    chat_mode="best",
                    similarity_top_k=5,
                    memory=memory,
                    context_prompt=(
                        f"You are {client.user.name}, a Discord bot, format responses as such."
                        "\nTopic: OpenPilot and its various forks."
                        "\n\nRelevant documents for the context:\n"
                        "{context_str}"
                        "\n\nInstruction: Use the previous chat history or the context above to interact and assist the user."
                        "\nALWAYS provide the link to the source of the information if applicable."
                    )
                )
                chat_response = await asyncio.to_thread(chat_engine.chat, content)
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