# modules.utils.GPT

from modules.utils.commons import send_long_message, fetch_reply_chain, HistoryChatMessage
from llama_index.core import StorageContext, Settings, VectorStoreIndex, SimpleDirectoryReader
from llama_index.readers.github import GithubClient, GithubRepositoryReader
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.core.llms import MessageRole as Role
from llama_index.retrievers.bm25 import BM25Retriever
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.llms.openai import OpenAI
from llama_index.llms.gemini import Gemini
from dotenv import load_dotenv
from datetime import date
import asyncio
import openai
import httpx
import json
import sys
import re
import os
safety_settings = {
    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE"
}
load_dotenv()
#openai.api_key = os.getenv('OPENAI_API_KEY')
os.environ["GOOGLE_API_KEY"] = os.getenv('GOOGLE_API_KEY')
github_client = GithubClient(os.getenv('GITHUB_TOKEN'))
Settings.llm = Gemini(model_name="models/gemini-pro", max_tokens=1000, safety_settings=safety_settings)
Settings.embed_model = GeminiEmbedding(model_name="models/embedding-001")
# Settings.llm = OpenAI(model="gpt-4-turbo-preview", max_tokens=1000)
# Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")

local_dir = "./local_docs/"
persist_dir = "./local_vectors"
if not os.path.exists(persist_dir):
    print("Initialized successfully. Setting up vector store index...")
    repos_config = [
        {
            "owner": "twilsonco",
            "repo": "openpilot",
            "branch": "log-info",
            "filter_directories": (["sec"], GithubRepositoryReader.FilterType.INCLUDE),
            "filter_file_extensions": ([".md"], GithubRepositoryReader.FilterType.INCLUDE),
        },
        {
            "owner": "commaai",
            "repo": "openpilot-docs",
            "branch": "master",
            "filter_directories": (["docs"], GithubRepositoryReader.FilterType.INCLUDE),
            "filter_file_extensions": ([".md"], GithubRepositoryReader.FilterType.INCLUDE),
        },
        {
            "owner": "commaai",
            "repo": "comma10k",
            "branch": "master",
            "filter_directories": (["imgs", "imgs2", "imgsd", "masks", "masks2", "masksd"], GithubRepositoryReader.FilterType.EXCLUDE),
            "filter_file_extensions": ([".png", ".jpg"], GithubRepositoryReader.FilterType.EXCLUDE),
        },
        {
            "owner": "FrogAi",
            "repo": "FrogPilot",
            "branch": "FrogPilot-Development",
            "filter_directories": (["selfdrive", "README.md", "docs", "tools"], GithubRepositoryReader.FilterType.INCLUDE),
            "filter_file_extensions": ([".py", ".md", ".h", ".cc"], GithubRepositoryReader.FilterType.INCLUDE),
        },
        {
            "owner": "dragonpilot-community",
            "repo": "dragonpilot",
            "branch": "beta3",
            "filter_directories": (["CHANGELOGS.md", "README.md"], GithubRepositoryReader.FilterType.INCLUDE),
            "filter_file_extensions": ([".py", ".md", ".h", ".cc"], GithubRepositoryReader.FilterType.INCLUDE),
        },
        {
            "owner": "sunnypilot",
            "repo": "sunnypilot",
            "branch": "dev-c3",
            "filter_directories": (["CHANGELOGS.md", "README.md"], GithubRepositoryReader.FilterType.INCLUDE),
            "filter_file_extensions": ([".py", ".md", ".h", ".cc"], GithubRepositoryReader.FilterType.INCLUDE),
        },
    ]
    if not os.path.exists(local_dir):
        os.makedirs(local_dir, exist_ok=True)

    for config in repos_config:
        try:
            loader = GithubRepositoryReader(
                github_client,
                owner=config["owner"],
                repo=config["repo"],
                filter_directories=config["filter_directories"],
                filter_file_extensions=config["filter_file_extensions"],
                verbose=True,
                concurrent_requests=10,
                timeout=10,
                retries=3,
            )
            documents = loader.load_data(branch=config["branch"])
            for doc in documents:
                with open(os.path.join(local_dir, f"{doc.doc_id}.txt"), "w") as f:
                    json.dump(doc.to_dict(), f)
        except httpx.ConnectTimeout:
            print(f"Connection timeout for {config['owner']}/{config['repo']}.", file=sys.stderr)
            sys.exit(1)
    docs = SimpleDirectoryReader(local_dir).load_data()
    index = VectorStoreIndex.from_documents(docs)
    index.storage_context.persist(persist_dir=persist_dir)
    print("Index setup complete.")
else:
    print("Loading index from disk...")
    storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
    documents = SimpleDirectoryReader(local_dir).load_data()
    index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)
    print("Index setup complete.")

vector_retriever = index.as_retriever(similarity_top_k=4)
bm25_retriever = BM25Retriever.from_defaults(docstore=index.docstore, similarity_top_k=4)

retriever = QueryFusionRetriever(
    [vector_retriever, bm25_retriever],
    similarity_top_k=4,
    num_queries=2,
    mode="reciprocal_rerank",
    use_async=True,
    verbose=True,
)

async def process_message_with_llm(message, client):
    content = message.content.replace(client.user.mention, '').strip()
    if content:
        try:
            async with message.channel.typing():
                memory = ChatMemoryBuffer.from_defaults(token_limit=8192)
                context = await fetch_reply_chain(message)
                memory.set(context + [HistoryChatMessage(f"{content}", Role.USER)])
                chat_engine = CondensePlusContextChatEngine.from_defaults(
                    memory=memory,
                    retriever=retriever,
                    context_prompt=(
                        f"You are {client.user.name}, a Discord bot."
                        "\nTopic: OpenPilot and its various forks."
                        f"\nDate: {date.today().isoformat()}"
                        "\n\nRelevant documents for the context:\n"
                        "{context_str}"
                        "\n\nInstruction: Use the previous chat history or the context above to interact and assist the user."
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