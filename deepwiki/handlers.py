import logging
from typing import Any
from pydantic import BaseModel
from .models import FileContent, Reference
from .models import QueryResponse

logger = logging.getLogger(__name__)

class BaseHandler:
    """Base handler interface with standardized validation."""
    def handle(self, data: Any, response: QueryResponse) -> None:
        """Process data and update response.
        
        Args:
            data: Input data to process
            response: QueryResponse to update
            
        Raises:
            ValueError: If data is invalid
        """
        validated_data = self.validate(data)
        self.process(validated_data, response)

    def validate(self, data: Any) -> BaseModel:
        """Validate and normalize input data."""
        raise NotImplementedError

    def process(self, data: BaseModel, response: QueryResponse) -> None:
        """Process validated data and update response."""
        raise NotImplementedError

class FileContentsHandler(BaseHandler):
    def validate(self, data: Any) -> FileContent:
        if isinstance(data, FileContent):
            return data
        elif isinstance(data, dict):
            return FileContent.parse_obj(data)
        elif isinstance(data, list) and len(data) >= 3:
            return FileContent(
                repo=data[0],
                path=data[1], 
                content_preview=data[2][:200] + "..."
            )
        raise ValueError(f"Invalid file content data: {data}")

    def process(self, data: FileContent, response: QueryResponse) -> None:
        response.file_contents.append(data.dict())

class ReferenceHandler(BaseHandler):
    def validate(self, data: Any) -> Reference:
        if isinstance(data, Reference):
            return data
        elif isinstance(data, dict):
            # Attempt to parse the dictionary as a Reference
            try:
                return Reference.parse_obj(data)
            except Exception as e: # Catch potential Pydantic validation errors
                raise ValueError(f"Invalid reference dictionary data: {e}")
        # Raise error for unexpected types instead of fallback
        raise ValueError(f"Invalid reference data type: Expected dict or Reference, got {type(data)}")

    def process(self, data: Reference, response: QueryResponse) -> None:
        response.references.append(data)

class ListAppendHandler(BaseHandler):
    """Handler for appending items to list fields."""
    def __init__(self, field_name: str) -> None:
        self.field_name = field_name

    def validate(self, data: Any) -> list:
        if isinstance(data, list):
            return data
        raise ValueError(f"Expected list, got {type(data)}")

    def process(self, data: list, response: QueryResponse) -> None:
        getattr(response, self.field_name).extend(data)

class ChunkHandler(BaseHandler):
    """Handler for processing text chunks."""
    def validate(self, data: Any) -> str:
        if isinstance(data, str):
            return data
        return str(data)

    def process(self, data: str, response: QueryResponse) -> None:
        response.raw_answer += data

class LoggingHandler(BaseHandler):
    """Handler for logging messages."""
    def __init__(self, message: str) -> None:
        self.message = message

    def validate(self, data: Any) -> Any:
        return data  # No validation needed for logging

    def process(self, data: Any, response: QueryResponse) -> None:
        logger.info(self.message)