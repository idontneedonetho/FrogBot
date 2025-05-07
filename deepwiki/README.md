# DeepWiki Client

## Overview
DeepWiki is a Python client for knowledge search and retrieval, featuring real-time WebSocket communication, structured data models, and modular message handling. The client provides both a command line interface and a programmatic API for querying the DeepWiki knowledge base with streaming results.

## Core Features
- Real-time streaming of search results via WebSocket
- Configurable message processing pipeline
- Structured response handling with formatted answers, code, and references
- Modular design with clear separation of concerns
- Comprehensive error handling
- Example CLI and API usage

## Project Structure

### cli.py
Command line interface for DeepWiki queries. Key components:
- `StreamingState` class: Manages state during streaming responses
- `_format_reference()`: Formats file references
- `_print_answer()`: Prints answers with references
- `_print_live_result()`: Handles streaming output formatting
- `main()`: Entry point for CLI execution

### deepwiki.py
Core client implementation for API interactions. Key components:
- `DeepWikiConfig`: Configuration settings
- `MessageHandlerRegistry`: Manages message handlers (Strategy pattern)
- `DeepWikiClient`: Main client class with query functionality (Facade pattern)
- Key methods:
  - `query()`: Main public query method
  - `_stream_and_process_websocket()`: Handles WebSocket communication (Observer pattern)
  - `_process_websocket_message()`: Processes incoming messages

### example.py
Demonstrates DeepWikiClient usage:
- Basic query structure
- Response handling
- Configuration examples

### handlers.py
Message handlers for WebSocket messages (Handler pattern). Key components:
- `BaseHandler`: Abstract base class
- Specialized handlers for different message types (FileContents, Reference, etc.)
- Standardized validation and processing with type checking

### models.py
Data models and structures using Pydantic. Key components:
- `QueryResponse`: Main response container
- `FileContent`, `Reference`, `WebSocketMessage`: Data models
- Provides validation and standardized data formats

### websocket_manager.py
WebSocket connection management (Client-Server pattern). Key components:
- `WebSocketManager`: Handles connection lifecycle
- Features SSL/TLS support, timeout handling, and callback-based processing

## Component Interactions
- `cli.py` uses `DeepWikiClient` from `deepwiki.py` to execute queries
- `deepwiki.py` coordinates:
  - `models.py` for data structures
  - `handlers.py` for message processing
  - `websocket_manager.py` for connection management
- `example.py` demonstrates direct usage of `DeepWikiClient`

## Usage

### Command Line Interface
Run the CLI with:
```bash
python cli.py [query]
```

### Using DeepWikiClient
Example usage (as shown in example.py):
```python
from deepwiki import DeepWikiClient

client = DeepWikiClient()
response = client.query("Your search query")
```

## Dependencies
- websocket-client (for WebSocket communication)
- requests (for HTTP API calls)
- Pydantic (for data models and validation)