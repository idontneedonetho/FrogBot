
from llama_index.core import VectorStoreIndex, StorageContext, SimpleDirectoryReader
from llama_index.readers.github import GithubClient, GithubRepositoryReader
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from qdrant_client import QdrantClient
from dotenv import load_dotenv
import httpx
import sys
import os

load_dotenv()
github_client = GithubClient(os.getenv('GITHUB_TOKEN'))
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
        "branch": "gh-pages",
        "filter_directories": (["docs"], GithubRepositoryReader.FilterType.INCLUDE),
        "filter_file_extensions": ([".png", ".jpg"], GithubRepositoryReader.FilterType.EXCLUDE),
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
        "filter_directories": (["selfdrive", "CHANGELOGS.md", "README.md", "docs", "tools"], GithubRepositoryReader.FilterType.INCLUDE),
        "filter_file_extensions": ([".py", ".md", ".h", ".cc"], GithubRepositoryReader.FilterType.INCLUDE),
    },
    {
        "owner": "dragonpilot-community",
        "repo": "dragonpilot",
        "branch": "beta3",
        "filter_directories": (["selfdrive", "CHANGELOGS.md", "README.md"], GithubRepositoryReader.FilterType.INCLUDE),
        "filter_file_extensions": ([".py", ".md", ".h", ".cc"], GithubRepositoryReader.FilterType.INCLUDE),
    },
    {
        "owner": "sunnypilot",
        "repo": "sunnypilot",
        "branch": "dev-c3",
        "filter_directories": (["selfdrive", "CHANGELOGS.md", "README.md"], GithubRepositoryReader.FilterType.INCLUDE),
        "filter_file_extensions": ([".py", ".md", ".h", ".cc"], GithubRepositoryReader.FilterType.INCLUDE),
    },
]

all_docs = {}

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
        if "branch" in config:
            github_docs = loader.load_data(branch=config["branch"])
        all_docs[config['repo']] = github_docs
        print(f"Documents from {config['repo']} loaded successfully.")
        print(f"Current length of all_docs: {sum(len(v) for v in all_docs.values())}")
    except httpx.ConnectTimeout:
        print(f"Connection timeout for {config['owner']}/{config['repo']}.", file=sys.stderr)
        sys.exit(1)

embed_model = OpenAIEmbedding(model="text-embedding-3-small")

local_directory_reader = SimpleDirectoryReader('openpilot.wiki')
local_docs = local_directory_reader.load_data()
all_docs['local'] = local_docs
print(f"Local documents loaded successfully and added to all_docs. Current document count: {sum(len(v) for v in all_docs.values())}")

print("Setting up Qdrant and vector store...")
client = QdrantClient(os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API'))
vector_store = QdrantVectorStore("openpilot-data", client=client)
storage_context = StorageContext.from_defaults(vector_store=vector_store)
all_docs_list = [doc for docs in all_docs.values() for doc in docs]
index = VectorStoreIndex.from_documents(all_docs_list, storage_context=storage_context, embed_model=embed_model)
print("Index setup complete.")