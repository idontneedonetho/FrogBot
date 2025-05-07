import ssl
import logging
from typing import Callable, Optional
import websocket
class WebSocketError(Exception):
    """Exception related to WebSocket operations."""
    pass

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages the WebSocket connection lifecycle."""
    def __init__(self, ssl_verify: bool, user_agent: str, origin: str) -> None:
        self.ssl_verify: bool = ssl_verify
        self.user_agent: str = user_agent
        self.origin: str = origin
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
        ssl_context = ssl.create_default_context() if self.ssl_verify else None
        try:
            self.connection = websocket.create_connection(
                ws_url,
                timeout=timeout,
                header=[f"User-Agent: {self.user_agent}"],
                origin=self.origin,
                sslopt={"cert_reqs": ssl.CERT_REQUIRED if self.ssl_verify else ssl.CERT_NONE, "check_hostname": self.ssl_verify} if ssl_context else {}
            )
            return True
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            raise WebSocketError(f"Failed to create WebSocket connection: {e}")

    def receive_messages(
        self,
        timeout: int,
        process_message: Callable[[str], None],
        on_update: Optional[Callable[[], None]] = None
    ) -> None:
        """Receive and process WebSocket messages.
        
        Args:
            timeout: Receive timeout in seconds
            process_message: Callback to handle each message
            on_update: Optional callback after each message processing
            
        Raises:
            WebSocketError: If connection times out
        """
        while True:
            try:
                message = self.connection.recv()
                if not message:
                    break
                process_message(message)
                if on_update:
                    on_update()
            except websocket.WebSocketTimeoutException:
                raise WebSocketError(f"Connection timed out after {timeout}s")
            except websocket.WebSocketConnectionClosedException:
                break
            except Exception as e:
                logger.warning(f"WebSocket receive error: {e}")
                break

    def close(self) -> None:
        """Close the WebSocket connection if open."""
        if self.connection and getattr(self.connection, 'connected', False):
            try:
                self.connection.close()
            except Exception:
                pass