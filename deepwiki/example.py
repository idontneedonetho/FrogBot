from .deepwiki import DeepWikiClient

if __name__ == "__main__":
    search_terms = "Differences in MTSC and VTSC. Short paragraph"
    context = ""
    client = DeepWikiClient()

    print(f"Querying DeepWiki with: {search_terms!r}...")
    
    if response := client.query(
        search_terms=search_terms,
        context=context
    ):
        format_options = {
            'query_response': response,
            'display_raw': False,
            'display_filtered': True,
            'filter_show_text': True,
            'filter_show_markers': False,
            'filter_show_newlines': True,
            'display_references': True,
            'display_query_id': False,
            'display_query_url': True
        }
        print(client.format_query_response(**format_options))

    else:
        print("Query failed or returned no response.")