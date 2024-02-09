# GPT.py

import asyncio
from modules.utils.search import handle_query, estimate_confidence
from modules.utils.commons import send_long_message, fetch_reply_chain, fetch_message_from_link, ChatMessage, Role
from llama_index import (
    ServiceContext,
    VectorStoreIndex,
    StorageContext,
    SimpleDirectoryReader,
)
from llama_index.embeddings import OpenAIEmbedding
from llama_index.vector_stores import QdrantVectorStore
from qdrant_client import QdrantClient
from llama_index.llms import OpenAI
from llama_index.memory import ChatMemoryBuffer
import vertexai
from vertexai.preview.generative_models import GenerativeModel
import openai
import os
from dotenv import load_dotenv

load_dotenv()
vertexai.init(project=os.getenv('VERTEX_PROJECT_ID'))
openai.api_key = os.getenv('OPENAI_API_KEY')

index_loaded = False
try:
    print("Initializing Qdrant client and loading documents...")
    client = QdrantClient(
        os.getenv('QDRANT_URL'),
        api_key=os.getenv('QDRANT_API'),
    )
    documents = SimpleDirectoryReader("data").load_data()
    print("Setting up vector store and initializing OpenAI model...")
    vector_store = QdrantVectorStore(client=client, collection_name="openpilot-data")
    embed_model = OpenAIEmbedding(model="text-embedding-3-small")
    llm = OpenAI(model="gpt-4-turbo-preview")
    print("Setting up storage and service context...")
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    service_context = ServiceContext.from_defaults(embed_model=embed_model, llm=llm, chunk_overlap=24, chunk_size=1024)
    print("Attempting to load vector store index...")
    bit = 0
    if bit == 0:
        index = VectorStoreIndex.from_vector_store(vector_store, service_context=service_context)
        index_loaded = True
        print("Vector store index loaded successfully.")
    else:
        print("Failed to load vector store index, creating a new one...")
        index = VectorStoreIndex.from_documents(documents, storage_context, service_context)
        index_loaded = True
except Exception as e:
    print("Index not loaded, falling back to Vertex AI API LLM.", e)

async def process_message_with_llm(message, client):
    content = message.content.replace(client.user.mention, '').strip()
    if content:
        async with message.channel.typing():
            if index_loaded:
                memory = ChatMemoryBuffer.from_defaults(token_limit=4096)
                context = await fetch_reply_chain(message)
                combined_messages = [ChatMessage(msg.content, msg.role) for msg in context]
                combined_messages.append(ChatMessage(f"{message.author.name}: {content}", Role.USER))
                memory.set(combined_messages)
                chat_engine = index.as_chat_engine(
                    chat_mode="best",
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
            else:
                async with message.channel.typing():
                    if content.startswith('https://discord.com/channels/'):
                        linked_message = await fetch_message_from_link(client, content)
                        if linked_message:
                            context = await fetch_reply_chain(linked_message)
                            combined_messages = context
                            combined_messages.append(ChatMessage(linked_message.content, Role.USER))
                            response = await ask_gpt(client, combined_messages)
                            if not estimate_confidence(response):
                                print("Fetching additional information for uncertain queries.")
                                search_response, source_urls = await handle_query(linked_message.content)
                                response = await ask_gpt([ChatMessage(search_response, Role.USER)])
                                if source_urls:
                                    response += "\n\n" + source_urls
                                response = response if response else "I'm sorry, I couldn't find information on that topic."
                        else:
                            response = "I couldn't fetch the message from the link."
                    else:
                        context = await fetch_reply_chain(message)
                        combined_messages = context
                        combined_messages.append(ChatMessage(content, Role.USER))
                        response = await ask_gpt(client, combined_messages)
                        if not estimate_confidence(response):
                            print("Fetching additional information for uncertain queries.")
                            search_response, source_urls = await handle_query(content)
                            response = await ask_gpt([ChatMessage(search_response, Role.USER)])
                            if source_urls:
                                response += "\n\n" + source_urls
                            response = response if response else "I'm sorry, I couldn't find information on that topic."
                    response = response.replace(client.user.name + ":", "").strip()
                    await send_long_message(message, response)
                              
async def ask_gpt(client, input_messages, retry_attempts=3, delay=1, bit_flip=1):
    bot_name = client.user.name
    context = f"I am {bot_name}, a Discord bot. I can interact with users via text, and provide assistance with various tasks and queries. I am aware of the text-based functionalities of Discord and can perform actions accordingly, while keeping my responses concise and under 2000 characters."
    gemini_context = context + " I am powered by Gemini-Pro."
    gpt_context = ChatMessage(context + " I am powered by GPT-4 Turbo.", Role.SYSTEM)
    modified_input_messages = [gpt_context] + input_messages
    for attempt in range(retry_attempts):
        try:
            if bit_flip:
                response = openai.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[message.__dict__ for message in modified_input_messages]
                )
                response_message = response.choices[0].message.content
            else:
                model = GenerativeModel(model_name="gemini-pro")
                chat = model.start_chat()
                gemini_input_messages = [gemini_context]
                for msg in input_messages:
                    gemini_input_messages.append(msg.content)
                gemini_input_messages = [str(msg) for msg in gemini_input_messages]
                gemini_input_message_str = "\n".join(gemini_input_messages)
                response = chat.send_message(gemini_input_message_str)
                response_message = response.text
            return response_message
        except Exception as e:
            print(f"Error in ask_gpt with OpenAI API: {e}")
            if attempt < retry_attempts - 1:
                await asyncio.sleep(delay)
                continue
            try:
                if bit_flip:
                    model = GenerativeModel(model_name="gemini-pro")
                    chat = model.start_chat()
                    gemini_input_messages = [gemini_context]
                    for msg in input_messages:
                        gemini_input_messages.append(msg.content)
                    gemini_input_messages = [str(msg) for msg in gemini_input_messages]
                    gemini_input_message_str = "\n".join(gemini_input_messages)
                    response = chat.send_message(gemini_input_message_str)
                    response_message = response.text
                else:
                    response = openai.chat.completions.create(
                        model="gpt-4-turbo-preview",
                        messages=[message.__dict__ for message in modified_input_messages]
                    )
                    response_message = response.choices[0].message.content
                return response_message
            except Exception as e:
                print(f"Error in ask_gpt with Google AI: {e}")
    return "I'm sorry, I couldn't process that due to an error in both services."