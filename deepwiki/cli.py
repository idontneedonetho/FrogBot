import sys
import re
# DeepWiki imports
from .deepwiki import DeepWikiClient, DeepWikiConfig
from .models import QueryResponse

class StreamingState:
    """Tracks state during streaming query results processing."""
    
    def __init__(self) -> None:
        self.last_answer = ""
        self.header_printed = False
        self.current_line = ""

streaming_state = StreamingState()

def _print_live_result(response: QueryResponse) -> None:
    """Handle and print live updates from streaming query results.
    
    Args:
        response: QueryResponse object containing streaming updates
    """
    global streaming_state
    
    # Print header once per query
    if not streaming_state.header_printed:
        print("\n=== Results ===\n")
        print("📝 Answer:", end="", flush=True)
        streaming_state.header_printed = True
    
    # Process streaming updates
    if response.raw_answer and response.raw_answer != streaming_state.last_answer:
        new_text = response.raw_answer
        
        # Clean markdown
        new_text = re.sub(r'^(?:#+\s*Answer:?\s*\n*)+', '', new_text)
        new_text = re.sub(r'\n+(?:#+\s*Answer:?\s*\n*)+', '\n', new_text)
        
        # Format Notes section
        new_text = re.sub(r'(?:^|\n)#+\s*Notes:?\s*\n', '\n\nNotes:\n', new_text)
        new_text = re.sub(r'^Notes:?\s*\n', '\n\nNotes:\n', new_text)
        
        # Clean headers
        new_text = re.sub(r'^#{1,3} (.*?)\s*\n', r'\n\1:\n', new_text)
        new_text = re.sub(r'\n+#{1,3} (.*?)\s*\n', r'\n\1:\n', new_text)
        
        # Fix formatting issues
        new_text = re.sub(r'(`[^`]+`)\1', r'\1', new_text)
        new_text = re.sub(r'(\w+)_t\1', r'\1', new_text)
        new_text = re.sub(r'`([^`]+)`', r'\1', new_text)
        
        # Normalize whitespace
        new_text = re.sub(r'\s+\.', '.', new_text)
        new_text = re.sub(r'\.\s*([A-Z])', r'. \1', new_text)
        new_text = re.sub(r'\n{3,}', '\n\n', new_text)
        
        # Format lists consistently
        def format_list_item(match):
            number = match.group(1)
            content = match.group(2)
            indent = match.group(0).startswith('\n  ') and '  ' or ''
            content = re.sub(r'`([^`]+)`', r'\1', content)
            return f'\n{indent}{number} {content}'
            
        # Normalize list formatting
        new_text = re.sub(r'\n\s*\d+\.\s*\n\s*\n', '', new_text)  # Remove empty list items
        new_text = re.sub(r'\n\s*(\d+\.)\s*([^\n]+)', format_list_item, new_text)  # Format numbered lists
        new_text = re.sub(r'\n\s*[-*]\s+([^\n]+)', r'\n• \1', new_text)  # Convert markdown lists to bullets
        
        new_text = re.sub(r'(?:\*\*|__)(.*?)(?:\*\*|__)', r'\1', new_text)
        new_text = re.sub(r'`([^`]+)`', r'\1', new_text)
        
        # Only print new content since last update
        if streaming_state.last_answer:
            # Find first difference between old and new text
            i = 0
            min_len = min(len(streaming_state.last_answer), len(new_text))
            while i < min_len and streaming_state.last_answer[i] == new_text[i]:
                i += 1
            
            # Print only new content
            if i < len(new_text):
                new_content = new_text[i:]
                # Skip if it would restart the content
                if not any(new_text[i:].startswith(x) for x in [
                    "## Answer", 
                    "# Answer"
                ]):
                    print(new_content, end="", flush=True)
        else:
            # Clean introductory text for first content
            clean_text = re.sub(r'^(?:I\'ll provide.*?\n+|Based on.*?\n+)', '', new_text)
            print(clean_text, end="", flush=True)
        
        streaming_state.last_answer = new_text
    
    # Process final results when complete
    if hasattr(response, 'done') and response.done:
        if response.summary_chunks:
            print("\n\n📑 Summaries:")
            for i, summary in enumerate(response.summary_chunks, 1):
                print(f"\nSummary {i}:\n{summary}")
        if response.code_chunks:
            print("\n💻 Code Chunks:")
            for chunk in response.code_chunks:
                path = chunk.get('relative_path', '?')
                start = chunk.get('start_line', '?')
                end = chunk.get('end_line', '?')
                print(f"\nFrom {path} (lines {start}-{end}):\n{chunk.get('text', '')}")
        if response.references:
            print("\n🔗 References:")
            for i, ref in enumerate(response.references, 1):
                url = ref.github_url
                if url:
                    display_path = ref._path if ref._path else ref.file_path
                    print(f"  {i}. Path: {display_path}")
                    print(f"     Lines: {ref.range_start}-{ref.range_end}")
                    print(f"     URL: {url}")
                else:
                    # Fallback if URL couldn't be generated
                    print(f"  {i}. Path: {ref.file_path}")
                    print(f"     Lines: {ref.range_start}-{ref.range_end}")

def main() -> None:
    """Run the DeepWiki CLI client with interactive input."""
    print("=== DeepWiki Client ===")
    search_terms = input("Search terms: ").strip()
    context = input("Context (e.g., wiki page): ").strip()
    if not (search_terms and context):
        print("Error: Search terms and context are required")
        sys.exit(1)

    global streaming_state
    streaming_state = StreamingState()
    
    client = DeepWikiClient(config=DeepWikiConfig())
    response = client.query(search_terms, context, on_update=_print_live_result)
    if not response:
        print("\n⚠️ Query failed")
        sys.exit(1)

if __name__ == "__main__":
    main()