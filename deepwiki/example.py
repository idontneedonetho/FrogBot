from .deepwiki import DeepWikiClient

# search_terms = "what to search for"
# context = "additional context about the query" 
response = DeepWikiClient().query(
    search_terms="short paragraph about speed limit controller", 
    context="overview of functionality"
)
print(response.raw_answer if response else "Query failed")

if response and response.references:
    print("\n--- References ---")
    for i, ref in enumerate(response.references, 1):
         url = ref.github_url
         if url:
             display_path = ref._path if ref._path else ref.file_path
             print(f"{i}. Path: {display_path}")
             print(f"   Lines: {ref.range_start}-{ref.range_end}")
             print(f"   URL: {url}")
         else:
             print(f"{i}. Path: {ref.file_path}")
             print(f"   Lines: {ref.range_start}-{ref.range_end}")