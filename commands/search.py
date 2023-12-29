# commands/search.py

import re
import os
import asyncio
import nltk
import trafilatura
import requests
import aiohttp
from commands import GPT
from googlesearch import search

def setup_nltk():
    try:
        nltk.data.find('taggers/averaged_perceptron_tagger')
    except LookupError:
        nltk.download('averaged_perceptron_tagger')
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')
    try:
        nltk.data.find('chunkers/maxent_ne_chunker')
    except LookupError:
        nltk.download('maxent_ne_chunker')
    try:
        nltk.data.find('corpora/words')
    except LookupError:
        nltk.download('words')
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords')
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

def search_google(query):
    try:
        results = search(query, num_results=1, advanced=True)
        for result in results:
            print(f"First URL found: {result.url}")
            return result.url
    except Exception as e:
        print(f"Error during Google search: {e}")
    return None

async def handle_query(query):
    print(f"Handling query: {query}")
    initial_response = await GPT.ask_gpt([{"role": "user", "content": query}], is_image=False)
    if estimate_confidence(initial_response):
        return initial_response
    else:
        search_url = search_google(query)
        if search_url:
            content = fetch_content_with_trafilatura(search_url)
            return f"Here's what I found about '{query}':\n{content}\n\n[Source: {search_url}]"
        else:
            return "No relevant results found for the query."
