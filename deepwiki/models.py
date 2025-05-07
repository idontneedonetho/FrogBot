import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, model_validator


@dataclass
class QueryResponse:
    """Dataclass holding the results of a DeepWiki query."""
    query_id: str
    file_contents: List['FileContent'] = field(default_factory=list)
    code_chunks: List[Any] = field(default_factory=list)
    summary_chunks: List[Any] = field(default_factory=list)
    raw_answer: str = ""
    references: List['Reference'] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    done: bool = False


class FileContent(BaseModel):
    """Represents file content with preview."""
    repo: str = Field(..., description="Repository name")
    path: str = Field(..., description="File path")
    content_preview: str = Field(..., description="Preview of file contents")


class Reference(BaseModel):
    """Represents a code location reference."""
    file_path: str = Field(..., description="Full repository path to file, e.g., 'Repo Owner/Name: path/to/file:0-0'")
    range_start: int = Field(..., description="Start line number of the reference")
    range_end: int = Field(..., description="End line number of the reference")

    # Internal fields to store parsed components
    _owner: Optional[str] = None
    _repo: Optional[str] = None
    _path: Optional[str] = None

    @model_validator(mode='after')
    def _parse_file_path_components(self) -> 'Reference':
        """Parse the owner, repo, and path from the file_path string after validation."""
        if not self.file_path:
            return self # Nothing to parse if file_path is empty/None

        # Regex to capture Owner, Repo, and Path from "Repo Owner/RepoName: PathToFile..."
        match = re.match(r"Repo\s+([^/]+)/([^:]+):\s*([^:]+)(?::\d+-\d+)?$", self.file_path)
        if match:
            self._owner = match.group(1)
            self._repo = match.group(2)
            self._path = match.group(3)
        else:
            # Fallback if format doesn't match (maintains original behavior)
            self._path = self.file_path
        return self

    @property
    def github_url(self) -> Optional[str]:
        """Constructs a GitHub permalink for the code reference."""
        if not (self._owner and self._repo and self._path and
                self.range_start is not None and self.range_end is not None):
            return None

        # Assuming repo name is the branch name (maintains original behavior)
        branch = self._repo
        base_url = f"https://github.com/{self._owner}/{self._repo}/blob/{branch}/{self._path}"

        # Add line numbers if the range is valid
        if 0 < self.range_start <= self.range_end:
            return f"{base_url}#L{self.range_start}-L{self.range_end}"
        else:
            # Return URL without line numbers for invalid ranges
            return base_url


class WebSocketMessage(BaseModel):
    """WebSocket message structure."""
    type: Optional[str] = Field(None, description="Message type identifier")
    data: Optional[Union[dict, list, str]] = Field(None, description="Message payload")
    title: Optional[str] = Field(None, description="Alternative type field")