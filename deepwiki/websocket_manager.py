import ssl
import logging
from typing import Callable, Optional
import websocket

class WebSocketError(Exception):
    """Exception related to WebSocket operations."""
    pass

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connection lifecycle with SSL verification."""
    
    def __init__(self, ssl_verify: bool, user_agent: str, origin: str) -> None:
        self.ssl_verify = ssl_verify
        self.user_agent = user_agent
        self.origin = origin
        self.connection: Optional[websocket.WebSocket] = None

    def connect(self, ws_url: str, timeout: int) -> bool:
        """Establish WebSocket connection.

        Args:
            ws_url: WebSocket URL to connect to
            timeout: Connection timeout in seconds

        Returns:
            True if connection succeeded

        Raises:
            WebSocketError: If connection fails
        """
        sslopt = self._get_ssl_options()

        try:
            self.connection = websocket.create_connection(
                ws_url,
                timeout=timeout,
                header=[f"User-Agent: {self.user_agent}"],
                origin=self.origin,
                sslopt=sslopt
            )
            return True
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            raise WebSocketError(f"Connection failed: {e}")

    def receive_messages(
        self,
        timeout: int,
        process_message: Callable[[str], None],
        on_update: Optional[Callable[[], None]] = None
    ) -> None:
        """Receive and process WebSocket messages until connection closes.

        Args:
            timeout: Receive timeout in seconds
            process_message: Callback to handle each message
            on_update: Optional callback after message processing

        Raises:
            WebSocketError: If connection times out
        """
        try:
            self._receive_messages_loop(process_message, on_update)
        except websocket.WebSocketTimeoutException:
            raise WebSocketError(f"Connection timed out after {timeout}s")
        except (websocket.WebSocketConnectionClosedException, Exception) as e:
            self._handle_receive_error(e)

    def close(self) -> None:
        """Close WebSocket connection if open."""
        if self._is_connection_active():
            try:
                self.connection.close()
            except Exception:
                pass

    def _get_ssl_options(self) -> dict:
        """Return SSL options based on verification setting."""
        if not self.ssl_verify:
            return {}
        return {
            'cert_reqs': ssl.CERT_REQUIRED,
            'check_hostname': True
        }

    def _receive_messages_loop(self, process_message, on_update) -> None:
        """Main message receiving loop."""
        while message := self.connection.recv():
            process_message(message)
            on_update and on_update()

    def _handle_receive_error(self, error: Exception) -> None:
        """Handle receive errors appropriately."""
        if not isinstance(error, websocket.WebSocketConnectionClosedException):
            logger.warning(f"WebSocket receive error: {error}")

    def _is_connection_active(self) -> bool:
        """Check if connection is still active."""
        return hasattr(self.connection, 'connected') and self.connection.connected