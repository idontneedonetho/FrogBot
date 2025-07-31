import re
import logging
from typing import Any, TypeVar, Generic
from pydantic import BaseModel
from .models import FileContent, Reference, QueryResponse
from .models import TextBlock, SearchMarkerBlock, NewlineBlock, ContentElement

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class BaseHandler(Generic[T]):
    """Abstract base handler for processing data and updating a response."""
    def handle(self, data: Any, response: QueryResponse) -> None:
        """Validate data then process it to update the response."""
        self.process(self.validate(data), response)

    def validate(self, data: Any) -> T:
        """Validate and normalize input data."""
        raise NotImplementedError

    def process(self, data: T, response: QueryResponse) -> None:
        """Process validated data."""
        raise NotImplementedError

class FileContentsHandler(BaseHandler[FileContent]):
    """Handler for file content data supporting multiple input formats."""
    def validate(self, data: Any) -> FileContent:
        """Validate file content from FileContent, dict, or list formats."""
        if isinstance(data, FileContent):
            return data
        if isinstance(data, dict):
            return FileContent.model_validate(data)
        if isinstance(data, list) and len(data) >= 3:
            preview = str(data[2])
            preview = f"{preview[:200]}..." if len(preview) > 200 else preview
            return FileContent(repo=data[0], path=data[1], content_preview=preview)
        raise ValueError(f"Invalid file content data: {type(data)}")

    def process(self, data: FileContent, response: QueryResponse) -> None:
        """Appends validated file content to the response."""
        response.file_contents.append(data.model_dump())

class ReferenceHandler(BaseHandler[Reference]):
    """Handler for reference data supporting Reference or dict inputs."""
    def validate(self, data: Any) -> Reference:
        """Validate reference data from Reference or dict formats.

        Args:
            data: Input data to validate

        Returns:
            Validated Reference object

        Raises:
            ValueError: If data format is invalid
        """
        if isinstance(data, Reference):
            return data
        if isinstance(data, dict):
            return Reference.model_validate(data)
        raise ValueError(f"Expected Reference or dict, got {type(data)}")

    def process(self, data: Reference, response: QueryResponse) -> None:
        """Appends validated reference to the response."""
        response.references.append(data)

class ListAppendHandler(BaseHandler):
    """Handler for appending items to a specified list field in the response."""
    def __init__(self, field_name: str) -> None:
        self.field_name = field_name

    def validate(self, data: Any) -> list:
        """Ensures input data is a list.

        Args:
            data: Input data to validate

        Returns:
            Validated list

        Raises:
            ValueError: If data is not a list
        """
        if isinstance(data, list):
            return data
        raise ValueError(f"Expected list, got {type(data)}")

    def process(self, data: list, response: QueryResponse) -> None:
        """Appends items from the input list to the target field in the response."""
        target_list = getattr(response, self.field_name)
        target_list += data

class ChunkHandler(BaseHandler[str]):
    """Handler for text chunks, splitting into semantic content blocks."""
    MARKER_STR = "> Searching codebase..."
    NEWLINE_PATTERN = re.compile(r'\n+')
    SPLIT_PATTERN = re.compile(f'({re.escape(MARKER_STR)}|\n+)')

    def validate(self, data: Any) -> str:
        """Convert input to string if not already.

        Args:
            data: Input data to convert

        Returns:
            String representation of input
        """
        return data if isinstance(data, str) else str(data)

    def process(self, data: str, response: QueryResponse) -> None:
        """Process text chunk into raw_answer and structured content elements."""
        if not hasattr(response, '_answer_parts'):
            response._answer_parts = [response.raw_answer]
        response._answer_parts.append(data)
        response.raw_answer = ''.join(response._answer_parts)
        
        for segment in filter(None, self.SPLIT_PATTERN.split(data)):
            if segment == self.MARKER_STR:
                response.content_elements.append(SearchMarkerBlock())
            elif self.NEWLINE_PATTERN.fullmatch(segment):
                response.content_elements.append(NewlineBlock(count=len(segment)))
            else:
                self._append_text_segment(segment, response.content_elements)

    def _append_text_segment(self, segment: str, elements: list[ContentElement]) -> None:
        """Append text segment, merging with previous TextBlock if possible.

        Args:
            segment: Text segment to append
            elements: List of content elements to modify
        """
        if elements and isinstance(elements[-1], TextBlock):
            elements[-1].content += segment
        else:
            elements.append(TextBlock(content=segment))

class LoggingHandler(BaseHandler[Any]):
    """Handler that simply logs a predefined message."""
    def __init__(self, message: str) -> None:
        self.message = message

    def validate(self, data: Any) -> Any:
        """No validation needed - pass through data."""
        return data

    def process(self, data: Any, response: QueryResponse) -> None:
        """Log the predefined message."""
        logger.info(self.message)