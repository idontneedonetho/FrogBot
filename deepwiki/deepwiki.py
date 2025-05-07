import re, uuid
import logging
from .models import WebSocketMessage, QueryResponse 
from pydantic import ValidationError
# Import handlers from handlers.py
from .handlers import (
    BaseHandler, 
    FileContentsHandler,
    ReferenceHandler,
    ListAppendHandler,
    ChunkHandler,
    LoggingHandler
)
# Import WebSocketManager and WebSocketError
from .websocket_manager import WebSocketManager, WebSocketError as WebSocketManagerError

logger = logging.getLogger(__name__)
from typing import Any, Callable, Dict, List, Optional
import requests 

class DeepWikiConfig:
    """Configuration settings for the DeepWiki client."""
    BASE_API_URL = "https://api.devin.ai/ada"
    QUERY_ENDPOINT = f"{BASE_API_URL}/query"
    WS_ENDPOINT_FORMAT = f"wss://{BASE_API_URL.split('://')[1]}/ws/query/{{query_id}}"
    SEARCH_URL_FORMAT = "https://deepwiki.com/search/{query_id}"
    DEFAULT_ORIGIN = "https://deepwiki.com"
    DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    DEFAULT_ENGINE_ID = "agent"
    # DEFAULT_ENGINE_ID = "multihop"
    DEFAULT_REPO = ["FrogAi/FrogPilot"]
    HTTP_TIMEOUT = 30
    WEBSOCKET_TIMEOUT = 120
    ssl_verify = True
    MSG_DONE: str = "Received 'done' message"
    MSG_LOADING_INDEXES: str = "Server is loading indexes..."


class DeepWikiError(Exception):
    """Base exception for DeepWiki client errors."""
    pass

class MessageHandlerRegistry:
    """Registry for mapping message types to handlers."""
    def __init__(self) -> None:
        # Use BaseHandler from handlers.py if defined, otherwise adjust type hint
        self.handlers: Dict[str, BaseHandler] = {}

    def register(self, message_type: str, handler: BaseHandler) -> None:
        """Register a message handler for a specific message type.
        
        Args:
            message_type: The type of message to handle
            handler: The handler instance for this message type
        """
        self.handlers[message_type] = handler

    def get(self, message_type: str) -> Optional[BaseHandler]:
        """Get the handler for a message type.
        
        Args:
            message_type: The type of message to get handler for
            
        Returns:
            The registered handler or None if not found
        """
        return self.handlers.get(message_type)

class DeepWikiClient:
    """Client for interacting with the DeepWiki API."""
    def __init__(self, config: DeepWikiConfig = None):
        """Initialize the DeepWiki client.
        
        Args:
            config: Optional configuration settings (uses defaults if None)
        """
        # Now uses the DeepWikiConfig defined above
        self.config = config or DeepWikiConfig() 
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.config.DEFAULT_USER_AGENT,
            'Origin': self.config.DEFAULT_ORIGIN
        })
        # Ensure ssl_verify is set on the config instance
        if not hasattr(self.config, 'ssl_verify'):
             self.config.ssl_verify = True # Set default if missing

        self.user_agent = self.config.DEFAULT_USER_AGENT
        self.origin = self.config.DEFAULT_ORIGIN
        self._message_handlers = MessageHandlerRegistry()
        # Register imported handlers
        self._message_handlers.register('file_contents', FileContentsHandler())
        self._message_handlers.register('code_chunks', ListAppendHandler('code_chunks'))
        self._message_handlers.register('summary_chunks', ListAppendHandler('summary_chunks'))
        self._message_handlers.register('chunk', ChunkHandler())
        self._message_handlers.register('done', LoggingHandler(self.config.MSG_DONE))
        self._message_handlers.register('reference', ReferenceHandler())
        self._message_handlers.register('loading_indexes', LoggingHandler(self.config.MSG_LOADING_INDEXES))

    def _generate_query_prefix(self, search_terms: str) -> str:
        p = re.sub(r'[^a-z0-9\s]', '', search_terms.lower().encode('ascii', 'ignore').decode())
        return re.sub(r'\s+', '-', p).strip('-')[:30]

    def _generate_query_details(self, search_terms: str, context: str, repos: Optional[List[str]] = None) -> Dict[str, Any]:
        query_id = f"{self._generate_query_prefix(search_terms)}_{uuid.uuid4()}"
        return {
            "payload": {
                "engine_id": self.config.DEFAULT_ENGINE_ID,
                "user_query": f"<relevant_context>{context}</relevant_context>{search_terms}",
                "query_id": query_id,
                "repo_names": repos or self.config.DEFAULT_REPO,
                "keywords": [],
                "additional_context": "",
                "use_notes": False,
                "generate_summary": False
            },
            "deepwiki_url": self.config.SEARCH_URL_FORMAT.format(query_id=query_id),
            "ws_url": self.config.WS_ENDPOINT_FORMAT.format(query_id=query_id),
            "query_id": query_id
        }

    def _make_api_request(self, url: str, method: str = 'GET', json_data: Optional[Dict[str, Any]] = None, timeout: Optional[int] = None) -> requests.Response:
        t = timeout if timeout is not None else self.config.HTTP_TIMEOUT
        try:
            # Pass verify=self.config.ssl_verify to requests
            r = self.session.request(method, url, json=json_data, timeout=t, verify=self.config.ssl_verify)
            r.raise_for_status()
            return r
        except requests.exceptions.Timeout:
            raise DeepWikiError(f"Request timed out after {t}s")
        except requests.exceptions.HTTPError as e:
            txt = e.response.text[:500] + ('...' if len(e.response.text) > 500 else '')
            raise DeepWikiError(f"HTTP {e.response.status_code}: {txt}")
        except requests.exceptions.RequestException as e:
            raise DeepWikiError(f"Network error: {e}")


    def _process_websocket_message(self, msg: str, response: QueryResponse) -> None:
        try:
            # Basic parsing to get type and data
            ws_msg = WebSocketMessage.parse_raw(msg)
            
            # Use message type or title if type is missing
            msg_type = ws_msg.type or ws_msg.title 
            if not msg_type:
                 logger.warning(f"WebSocket message missing type/title: {msg[:100]}...")
                 return

            handler = self._message_handlers.get(msg_type)
            if handler:
                # Let the handler manage validation and processing of ws_msg.data
                handler.handle(ws_msg.data, response)
            else:
                logger.debug(f"No handler registered for message type: {msg_type}")
        # Catch validation errors from Pydantic and other potential issues
        except (ValidationError, ValueError, Exception) as e:
            logger.warning(f"WebSocket message processing error: {e} - Message: {msg[:100]}...", exc_info=True)


    def _stream_and_process_websocket(
        self,
        ws_url: str,
        query_id: str,
        timeout: Optional[int] = None,
        on_update: Optional[Callable[[QueryResponse], None]] = None
    ) -> QueryResponse:
        t = timeout if timeout is not None else self.config.WEBSOCKET_TIMEOUT
        # Pass ssl_verify directly
        ws_manager = WebSocketManager(self.config.ssl_verify, self.user_agent, self.origin)
        response = QueryResponse(query_id=query_id)

        try:
            ws_manager.connect(ws_url, t)
            ws_manager.receive_messages(
                t,
                lambda msg: self._process_websocket_message(msg, response),
                lambda: on_update(response) if on_update else None
            )
            response.done = True
            if on_update:
                on_update(response)  # Final update with done=True
            return response
        # Catch specific WebSocket errors
        except WebSocketManagerError as e:
             logger.error(f"WebSocket operation failed: {e}")
             raise DeepWikiError(f"WebSocket error: {e}") from e
        finally:
            ws_manager.close()

    def _initiate_query(self, payload: Dict[str, Any]) -> None:
        self._make_api_request(self.config.QUERY_ENDPOINT, method='POST', json_data=payload)

    def query(self, search_terms: str, context: str, repos: Optional[List[str]] = None, on_update: Optional[Callable[[QueryResponse], None]] = None) -> Optional[QueryResponse]:
        """Execute a query against the DeepWiki API.
        
        Args:
            search_terms: The search query terms
            context: Additional context for the query
            repos: Optional list of repositories to search
            on_update: Optional callback for query progress updates
            
        Returns:
            QueryResponse with results, or None if query failed
        """
        try:
            d = self._generate_query_details(search_terms, context, repos)
            self._initiate_query(d['payload'])
            r = self._stream_and_process_websocket(d['ws_url'], d['query_id'], on_update=on_update)
            return r
        except DeepWikiError as e:
            logger.error(f"DeepWiki query failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during query: {e}")
            return None