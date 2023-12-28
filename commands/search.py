import re
import os
import asyncio
import nltk
import trafilatura
import requests
import aiohttp
from commands import GPT

# Download required NLTK data
nltk.download('averaged_perceptron_tagger')
nltk.download('punkt')
nltk.download('maxent_ne_chunker')
nltk.download('words')

def setup_nltk():
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
    print("NLTK setup complete.")

setup_nltk()

def extract_keywords(text):
    print("Extracting keywords...")
    words = re.findall(r'\b\w+\b', text.lower())
    stop_words = set(nltk.corpus.stopwords.words('english'))
    keywords = [word for word in words if word not in stop_words]
    print(f"Extracted keywords: {keywords}")
    return keywords

def fetch_content_with_trafilatura(url):
    print(f"Fetching content from URL: {url}")
    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        return trafilatura.extract(downloaded)
    else:
        print("Error: Unable to fetch content.")
        return None

def estimate_confidence(response):
    print("Estimating confidence in the response...")
    uncertain_phrases = ["do not have access to", "cannot provide", "I'm not sure", "I think", "possibly", "maybe", "it seems", "suggest using a search engine"]
    confidence = not any(phrase in response for phrase in uncertain_phrases)
    print(f"Confidence estimated: {'High' if confidence else 'Low'}")
    return confidence

async def google_custom_search(query):
    print(f"Performing Google Custom Search for query: {query}")
    api_key = os.getenv("SEARCH_API_KEY")
    search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
    url = f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={search_engine_id}&q={query}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            search_results = response.json()
            if 'items' in search_results and search_results['items']:
                first_url = search_results['items'][0].get('link')
                print(f"First URL found: {first_url}")
                return first_url
        print("Error or no results in Google Custom Search.")
    except Exception as e:
        print(f"Error during Google Custom Search: {e}")
    return None

async def handle_query(query, is_image=False):
    print(f"Handling query: {query}")
    if is_image:
        print("Received an image. Skipping internet search.")
        return "Image processing is not supported for internet search queries."
    else:
        initial_response = await GPT.ask_gpt([{"role": "user", "content": query}], is_image=False)
        if estimate_confidence(initial_response):
            print("Confident response obtained from GPT.")
            return initial_response
        else:
            print("Fetching additional information for the query.")
            search_results = await google_custom_search(query)
            if search_results and 'web' in search_results and search_results['web']['results']:
                first_url = search_results['web']['results'][0].get('url')
                if first_url:
                    content = fetch_content_with_trafilatura(first_url)
                    return f"Here's what I found about '{query}':\n{content}\n\n[Source: {first_url}]"
                else:
                    print("No URL found in search results.")
                    return "No relevant results found."
            else:
                print("No relevant results found for the query.")
                return "No relevant results found."
