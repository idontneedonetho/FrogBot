# commands/search.py

import re
import nltk
import trafilatura
import asyncio
import spacy
from commands import GPT
from googlesearch import search
from spacy.matcher import PhraseMatcher

nlp = spacy.load("en_core_web_sm")

matcher = PhraseMatcher(nlp.vocab)

fresh_info_keywords = ["latest", "newest", "current", "update", "now", "recent", "today"]
code_related_keywords = ["code", "programming", "algorithm", "syntax", "code sample"]
creative_writing_keywords = ["write", "story", "poem", "creative", "imagination"]

fresh_info_patterns = [nlp.make_doc(text) for text in fresh_info_keywords]
code_related_patterns = [nlp.make_doc(text) for text in code_related_keywords]
creative_writing_patterns = [nlp.make_doc(text) for text in creative_writing_keywords]

matcher.add("FreshInfo", fresh_info_patterns)
matcher.add("CodeRelated", code_related_patterns)
matcher.add("CreativeWriting", creative_writing_patterns)

def setup_nltk():
    nltk_packages = [
        ('averaged_perceptron_tagger', 'taggers/averaged_perceptron_tagger'),
        ('punkt', 'tokenizers/punkt'),
        ('maxent_ne_chunker', 'chunkers/maxent_ne_chunker'),
        ('words', 'corpora/words'),
        ('stopwords', 'corpora/stopwords')
    ]
    for package_name, package_location in nltk_packages:
        try:
            nltk.data.find(package_location)
        except LookupError:
            nltk.download(package_name)
setup_nltk()

def extract_keywords(text):
    stop_words = set(nltk.corpus.stopwords.words('english'))
    return ' '.join([word for word in re.findall(r'\b\w+\b', text.lower()) if word not in stop_words])

async def fetch_content_with_trafilatura(url):
    def fetch_content():
        content = trafilatura.extract(trafilatura.fetch_url(url))
        return content[:2000] if content else None
    return await asyncio.to_thread(fetch_content)

def search_google(query):
    try:
        GPT.rate_limited_request()
        results = search(query, num_results=1, advanced=True)
        return [result.url for result in results]
    except Exception as e:
        print(f"Error during Google search: {e}")
        return []

def estimate_confidence(response):
    uncertain_phrases = ["do not have access to", "do not have the ability to access real-time information", "do not have real-time capabilities", "cannot provide", "I'm not sure", "I think", "possibly", "maybe", "it seems", "suggest using a search engine"]
    return not any(phrase in response for phrase in uncertain_phrases)

def determine_information_type(query):
    doc = nlp(query.lower())
    matches = matcher(doc)
    for match_id, start, end in matches:
        rule_id = nlp.vocab.strings[match_id]
        if rule_id == "FreshInfo":
            return "Fresh Information"
        elif rule_id == "CodeRelated":
            return "Code-Related"
        elif rule_id == "CreativeWriting":
            return "Creative Writing"
    if any(ent.label_ in ["DATE", "TIME"] and 'recent' in ent.text.lower() for ent in doc.ents):
        return "Fresh Information"
    return "General Knowledge"

async def handle_query(query):
    print(f"Handling query: {query}")
    info_type = determine_information_type(query)
    initial_response = await GPT.ask_gpt([{"role": "user", "content": query}], is_image=False)
    if estimate_confidence(initial_response):
        return initial_response
    elif info_type == "Fresh Information" or not estimate_confidence(initial_response):
        search_urls = search_google(query)
        if search_urls:
            contents = await asyncio.gather(*(fetch_content_with_trafilatura(url) for url in search_urls))
            context = " ".join(content for content in contents if content)
            if context:
                combined_input = f"{query}\nContext: {context}"
                extended_response = await GPT.ask_gpt([{"role": "user", "content": combined_input}], is_image=False)
                source_urls = '\n'.join([f"[Source: {url}]" for url in search_urls])
                return extended_response + "\n\n" + source_urls
            else:
                return "I couldn't find any relevant information for your query."
        else:
            return "No relevant results found for the query."
