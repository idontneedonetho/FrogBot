# GPT.py

import openai
import os
from dotenv import load_dotenv
from llama_index import (
    ServiceContext,
    VectorStoreIndex,
    StorageContext,
    SimpleDirectoryReader,
)
from llama_index.chat_engine.condense_plus_context import CondensePlusContextChatEngine
from llama_index.embeddings import OpenAIEmbedding
from llama_index.vector_stores import QdrantVectorStore
from llama_index.memory import ChatMemoryBuffer
from qdrant_client import QdrantClient
from llama_index.llms import OpenAI
from modules.utils.commons import send_long_message, fetch_reply_chain, fetch_message_from_link, HistoryChatMessage, Role

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

try:
    client = QdrantClient(
        os.getenv('QDRANT_URL'),
        api_key=os.getenv('QDRANT_API'),
    )
    vector_store = QdrantVectorStore(client=client, collection_name="openpilot-data")
    embed_model = OpenAIEmbedding(model="text-embedding-3-small")
    llm = OpenAI(model="gpt-4-turbo-preview")
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    service_context = ServiceContext.from_defaults(embed_model=embed_model, llm=llm, chunk_overlap=24, chunk_size=1024)
    index = VectorStoreIndex.from_vector_store(vector_store, service_context=service_context)
except Exception as e:
    print("Index not loaded, falling back to Vertex AI API LLM.", e)

async def process_message_with_llm(message, client):
    content = message.content.replace(client.user.mention, '').strip()
    if content:
        async with message.channel.typing():
            memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
            context = await fetch_context_and_content(message, client, content)
            combined_messages = context
            combined_messages.append(HistoryChatMessage(f"{message.author.name}: {content}", Role.USER))
            memory.set(combined_messages)
            chat_engine = CondensePlusContextChatEngine.from_defaults(
                retriever=index.as_retriever(),
                memory=memory,
                similarity_top_k=5,
            )
            chat_response = chat_engine.chat(content)
            if chat_response:
                response_text = chat_response.response
                if response_text:
                    await send_long_message(message, response_text)
                else:
                    await message.channel.send("I didn't get a response.")
            else:
                await message.channel.send("There was an error processing the message.")

async def fetch_context_and_content(message, client, content):
    linked_message = await fetch_message_from_link(client, content) if content.startswith('https://discord.com/channels/') else message
    context = await fetch_reply_chain(linked_message)
    return context