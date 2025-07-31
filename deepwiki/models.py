import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, ClassVar, List, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator, computed_field

class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    content: str

class SearchMarkerBlock(BaseModel):
    type: Literal["search_marker"] = "search_marker"
    marker_text: Union[str, List[str]] = Field(
        default=["> Searching codebase...", r"(?i)^(let'?s?|now[,\s]*let'?s?).*:$"],
        description="Text patterns that identify search marker blocks"
    )

class NewlineBlock(BaseModel):
    type: Literal["newline"] = "newline"
    count: int = 1

class AgentThoughtBlock(BaseModel):
    type: Literal["agent_thought"] = "agent_thought"
    description: str

ContentElement = Union[TextBlock, SearchMarkerBlock, NewlineBlock, AgentThoughtBlock]

class BaseResponse:
    """Base class for response fields."""
    timestamp: datetime = field(default_factory=datetime.now)
    done: bool = False

@dataclass
class QueryResponse(BaseResponse):
    query_id: str
    file_contents: List['FileContent'] = field(default_factory=list)
    code_chunks: List[Any] = field(default_factory=list)
    summary_chunks: List[Any] = field(default_factory=list)
    raw_answer: str = ""
    content_elements: List[ContentElement] = field(default_factory=list)
    references: List['Reference'] = field(default_factory=list)

class FileContent(BaseModel):
    """Represents file content with repository metadata"""
    repo: str = Field(..., description="Repository name")
    path: str = Field(..., description="File path")
    content_preview: str = Field(..., description="Preview of file contents")

class Reference(BaseModel):
    """Represents a reference to a specific code location"""
    file_path: str = Field(..., description="Full repository path to file")
    range_start: int = Field(..., description="Start line number")
    range_end: int = Field(..., description="End line number")

    _owner: Optional[str] = None
    _repo: Optional[str] = None
    _path: Optional[str] = None
    FILE_PATH_REGEX: ClassVar[re.Pattern] = re.compile(
        r"^Repo\s+([^/]+)/([^:]+):\s*([^:]+)(?::\d+-\d+)?$"
    )
    GITHUB_BASE_URL: ClassVar[str] = "https://github.com"

    @model_validator(mode='after')
    def parse_file_path_components(self) -> 'Reference':
        """Parse file path into owner, repo and path components"""
        if not self.file_path:
            return self

        if match := self.FILE_PATH_REGEX.match(self.file_path):
            self._owner, self._repo, self._path = match.groups()
        else:
            self._path = self.file_path
        return self

    @computed_field
    @property
    def github_url(self) -> Optional[str]:
        """Generate GitHub URL for this reference"""
        if not (self._owner and self._repo and self._path):
            return None

        if 0 < self.range_start <= self.range_end:
            return f"{self.GITHUB_BASE_URL}/{self._owner}/{self._repo}/blob/{self._repo}/{self._path}#L{self.range_start}-L{self.range_end}"
        return f"{self.GITHUB_BASE_URL}/{self._owner}/{self._repo}/blob/{self._repo}/{self._path}"

class WebSocketMessage(BaseModel):
    """Basic WebSocket message structure"""
    type: Optional[str] = Field(None, description="Message type identifier")
    data: Optional[Union[dict, list, str]] = Field(None, description="Message payload")
    title: Optional[str] = Field(None, description="Alternative type field")