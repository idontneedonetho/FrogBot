import re
import uuid
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Union

import requests
from pydantic import ValidationError

from .models import WebSocketMessage, QueryResponse
from .models import TextBlock, SearchMarkerBlock, NewlineBlock
from .handlers import (
    FileContentsHandler,
    ReferenceHandler,
    ListAppendHandler,
    ChunkHandler,
    LoggingHandler
)
from .websocket_manager import WebSocketManager, WebSocketError as WebSocketManagerError

logger = logging.getLogger(__name__)


class DeepWikiConfig:
    """Configuration settings for the DeepWiki client."""
    BASE_API_URL: str = "https://api.devin.ai/ada"
    QUERY_ENDPOINT: str = f"{BASE_API_URL}/query"
    WS_ENDPOINT_FORMAT: str = f"wss://{BASE_API_URL.split('://')[1]}/ws/query/{{query_id}}"
    SEARCH_URL_FORMAT: str = "https://deepwiki.com/search/{query_id}"
    DEFAULT_ORIGIN: str = "https://deepwiki.com"
    DEFAULT_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0"
    DEFAULT_ENGINE_ID: str = "agent"
    DEFAULT_REPO: List[str] = ["FrogAi/FrogPilot"]
    HTTP_TIMEOUT: int = 30
    WEBSOCKET_TIMEOUT: int = 120
    SSL_VERIFY: bool = True
    MSG_DONE: str = "Received 'done' message"
    MSG_LOADING_INDEXES: str = "Server is loading indexes..."


class DeepWikiError(Exception):
    """Base exception for DeepWiki client errors."""
    pass


class DeepWikiClient:
    """Client for interacting with the DeepWiki API."""

    def __init__(self, config: Optional[DeepWikiConfig] = None):
        """Initialize the client with optional configuration."""
        self.config = config or DeepWikiConfig()
        self.session = requests.Session()
        self.session.headers.update(self._get_common_headers())
        self._init_message_handlers()

    def _init_message_handlers(self) -> None:
        """Initialize the message handlers dictionary."""
        self._message_handlers = {
            'file_contents': FileContentsHandler(),
            'code_chunks': ListAppendHandler('code_chunks'),
            'summary_chunks': ListAppendHandler('summary_chunks'),
            'chunk': ChunkHandler(),
            'done': LoggingHandler(self.config.MSG_DONE),
            'reference': ReferenceHandler(),
            'loading_indexes': LoggingHandler(self.config.MSG_LOADING_INDEXES),
        }

    def _get_common_headers(self) -> Dict[str, str]:
        """Return common headers for API requests."""
        return {
            'Origin': f"{self.config.DEFAULT_ORIGIN}",
            'Referer': f"{self.config.DEFAULT_ORIGIN}/",
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/json',
            'DNT': '1',
            'Sec-GPC': '1',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'Priority': 'u=0',
            'TE': 'trailers'
        }

    def generate_query_prefix(self, search_terms: str) -> str:
        """Generate a standardized query prefix from search terms."""
        return re.sub(r"[^a-z0-9-]", '', search_terms.lower().replace(' ', '-'))[:30]  # Keep only allowed chars and truncate

    def generate_query_details(
        self,
        search_terms: str,
        context: str,
        repos: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Generate payload and URL details for a query."""
        query_id = f"{self.generate_query_prefix(search_terms)}_{uuid.uuid4()}"
        payload = {
            "engine_id": self.config.DEFAULT_ENGINE_ID,
            "user_query": f"<relevant_context>{context}</relevant_context>{search_terms}",
            "query_id": query_id,
            "repo_names": repos or self.config.DEFAULT_REPO,
            "keywords": [],
            "additional_context": "",
            "use_notes": False,
            "generate_summary": False
        }
        return {
            "payload": payload,
            "deepwiki_url": self.config.SEARCH_URL_FORMAT.format(query_id=query_id),
            "ws_url": self.config.WS_ENDPOINT_FORMAT.format(query_id=query_id),
            "query_id": query_id
        }

    def _handle_api_response(self, response: requests.Response) -> requests.Response:
        """Handle common API response patterns and raise appropriate errors."""
        response.raise_for_status()
        
        if 200 <= response.status_code < 300:
            self._check_response_errors(response)
        
        return response

    def _check_response_errors(self, response: requests.Response) -> None:
        """Check response for common error patterns."""
        try:
            response_data = response.json()
            if not isinstance(response_data, dict):
                return

            if response_data.get('success') is False:
                raise DeepWikiError(f"API Error: {response_data.get('message', response.text)}")
            if 'error' in response_data:
                raise DeepWikiError(f"API Error: {response_data.get('error', response.text)}")
            if 'detail' in response_data and response.request.method == 'POST':
                if "Query not found" not in str(response_data.get('detail')):
                    raise DeepWikiError(f"API Error: {response_data.get('detail', response.text)}")
        except ValueError:
            pass  # Not JSON or not an error structure we recognize

    def make_api_request(
        self,
        url: str,
        method: str = 'GET',
        json_data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> requests.Response:
        """Make an API request with proper error handling."""
        try:
            headers = self._get_common_headers()
            response = self.session.request(
                method, url,
                json=json_data,
                headers=headers,
                timeout=timeout or self.config.HTTP_TIMEOUT,
                verify=self.config.SSL_VERIFY
            )
            return self._handle_api_response(response)
        except requests.exceptions.Timeout as e:
            raise DeepWikiError(f"Request timed out after {timeout or self.config.HTTP_TIMEOUT}s")
        except requests.exceptions.HTTPError as e:
            error_text = e.response.text[:500] + ('...' * (len(e.response.text) > 500))
            raise DeepWikiError(f"HTTP {e.response.status_code}: {error_text}")
        except requests.exceptions.RequestException as e:
            raise DeepWikiError(f"Network error: {e}")

    def process_websocket_message(self, msg: str, response: QueryResponse) -> None:
        """Process a WebSocket message using the appropriate handler."""
        try:
            ws_msg = WebSocketMessage.parse_raw(msg)
            if not (msg_type := ws_msg.type or ws_msg.title):
                logger.warning(f"WebSocket message missing type/title: {msg[:100]}...")
                return

            if handler := self._message_handlers.get(msg_type):
                handler.handle(ws_msg.data, response)
            else:
                logger.debug(f"No handler registered for message type: {msg_type}")
        except (ValidationError, ValueError) as e:
            logger.warning(f"WebSocket message parsing error: {e} - Message: {msg[:100]}...")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e} - Message: {msg[:100]}...")

    def stream_and_process_websocket(
        self,
        ws_url: str,
        query_id: str,
        timeout: Optional[int] = None,
        on_update: Optional[Callable[[QueryResponse], None]] = None
    ) -> QueryResponse:
        """Stream and process WebSocket messages for a query."""
        ws_manager = WebSocketManager(
            self.config.SSL_VERIFY,
            self.config.DEFAULT_USER_AGENT,
            self.config.DEFAULT_ORIGIN
        )
        query_response = QueryResponse(query_id=query_id)

        try:
            ws_manager.connect(ws_url, timeout or self.config.WEBSOCKET_TIMEOUT)
            ws_manager.receive_messages(
                timeout or self.config.WEBSOCKET_TIMEOUT,
                lambda msg: self.process_websocket_message(msg, query_response),
                lambda: on_update and on_update(query_response)
            )
            query_response.done = True
            if on_update:
                on_update(query_response)
            return query_response
        except WebSocketManagerError as e:
            logger.error(f"WebSocket error: {e}")
            raise DeepWikiError(f"WebSocket error: {e}") from e
        finally:
            ws_manager.close()

    def query(
        self,
        search_terms: str,
        context: str,
        repos: Optional[List[str]] = None,
        on_update: Optional[Callable[[QueryResponse], None]] = None
    ) -> Optional[QueryResponse]:
        """Execute a query and process the results."""
        try:
            query_details = self.generate_query_details(search_terms, context, repos)
            
            post_response = self.make_api_request(
                self.config.QUERY_ENDPOINT,
                'POST',
                query_details['payload']
            )
            post_data = post_response.json()
            if not post_data.get('status') == 'success':
                raise DeepWikiError(f"Query registration failed: {post_data}")

            # Exponential backoff for query processing (max 3 attempts, starting at 1s)
            for attempt in range(3):
                time.sleep(1 * (attempt + 1))
                status_check = self.make_api_request(
                    f"{self.config.QUERY_ENDPOINT}/{query_details['query_id']}"
                )
                if status_check.json().get('status') == 'ready':
                    break
            
            return self.stream_and_process_websocket(
                query_details['ws_url'],
                query_details['query_id'],
                on_update=on_update
            )
        except DeepWikiError as e:
            logger.error(f"Query failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected query error: {e}")
            return None

    def _matches_any_marker(self, text: str) -> bool:
        """Check if text matches any marker pattern."""
        # Use default marker patterns
        patterns = ["> Searching codebase...", r"(?i)^(let'?s?|now[,\s]*let'?s?).*:$"]
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False

    def _should_include_element(
        self,
        element: Union[TextBlock, SearchMarkerBlock, NewlineBlock],
        filter_show_text: bool,
        filter_show_markers: bool,
        filter_show_newlines: bool
    ) -> bool:
        """Determine if an element should be included in the formatted output."""
        if isinstance(element, TextBlock):
            return filter_show_text and not (not filter_show_markers and self._matches_any_marker(element.content.strip()))
        elif isinstance(element, SearchMarkerBlock):
            return filter_show_markers and not self._matches_any_marker(
                element.marker_text[0] if isinstance(element.marker_text, list) else element.marker_text
            )
        elif isinstance(element, NewlineBlock):
            return filter_show_newlines
        return False

    def _clean_text(self, text: str) -> str:
        """Clean text by normalizing and collapsing excessive line breaks.
        
        Args:
            text: Input text to clean
            
        Returns:
            Cleaned text with normalized line endings and collapsed excessive newlines
        """
        # 1. Normalize \r\n to \n
        text = re.sub(r'\r\n', '\n', text)
        # 2. Remove lines with only spaces/tabs between newlines
        text = re.sub(r'\n[ \t]+\n', '\n\n', text)
        # 3. Collapse three or more newlines to two
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    def _format_element_content(
        self,
        element: Union[TextBlock, SearchMarkerBlock, NewlineBlock],
        consecutive_newlines: int,
        max_newlines: int
    ) -> Optional[str]:
        """Format the content of a single element for output."""
        if isinstance(element, TextBlock):
            text = element.content.rstrip('\n')
            return text if text else None
        elif isinstance(element, SearchMarkerBlock):
            marker_text = element.marker_text[0] if isinstance(element.marker_text, list) else element.marker_text
            return marker_text.rstrip('\n') if marker_text else None
        elif isinstance(element, NewlineBlock):
            return "\n" if consecutive_newlines < max_newlines else None
        return None

    def format_query_response(
        self,
        query_response: QueryResponse,
        display_raw: bool = True,
        display_filtered: bool = True,
        filter_show_text: bool = True,
        filter_show_markers: bool = False,
        filter_show_newlines: bool = True,
        display_references: bool = True,
        display_query_id: bool = True,
        display_query_url: bool = True
    ) -> Optional[str]:
        """Format the query response according to specified display options."""
        if not query_response:
            return None

        output_parts = []
        consecutive_newlines = 0
        max_newlines = 2

        # Add query metadata if requested
        if display_query_id:
            output_parts.append(f"Query ID: {query_response.query_id}")
        if display_query_url:
            output_parts.append(f"Query URL: {self.config.SEARCH_URL_FORMAT.format(query_id=query_response.query_id)}")
        
        if (display_query_id or display_query_url) and any([
            display_raw and query_response.raw_answer,
            display_filtered and query_response.content_elements,
            display_references and query_response.references
        ]):
            output_parts.append("")

        # Add raw answer if requested
        if display_raw and query_response.raw_answer:
            output_parts.append(query_response.raw_answer.rstrip('\n'))

        # Add filtered content if requested
        if display_filtered and query_response.content_elements:
            for element in query_response.content_elements:
                if not self._should_include_element(element, filter_show_text, 
                                                  filter_show_markers, filter_show_newlines):
                    continue

                content = self._format_element_content(element, consecutive_newlines, max_newlines)
                if content is not None:
                    output_parts.append(content)
                    if content != "\n":
                        consecutive_newlines = 0
                    elif content == "\n":
                        consecutive_newlines += 1

            if output_parts:
                full_text = "\n".join(str(p) for p in output_parts if p is not None)
                output_parts = [self._clean_text(full_text)]

        # Add references if requested
        if display_references and query_response.references:
            if output_parts and output_parts[0].strip():
                content_str = output_parts[0]
                if content_str.endswith("\n\n"):
                    pass
                elif content_str.endswith("\n"):
                    output_parts[0] = content_str + "\n"
                else:
                    output_parts[0] = content_str + "\n\n"

            for i, ref in enumerate(query_response.references, 1):
                path = ref._path or ref.file_path
                line_range = f"{ref.range_start}-{ref.range_end}"
                ref_str = f"{i}. Path: {path} (Lines {line_range})"
                if ref.github_url:
                    ref_str += f" - {ref.github_url}"
                output_parts.append(ref_str)

        return "\n".join(output_parts) if output_parts else None
