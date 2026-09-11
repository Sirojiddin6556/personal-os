"""Cursor-based pagination models and utilities."""

import base64
import json
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """Query parameters for cursor-based pagination."""

    cursor: Optional[str] = Field(
        default=None,
        description="Opaque cursor for pagination offset",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items to return per page (max 100)",
    )
    direction: str = Field(
        default="forward",
        pattern="^(forward|backward)$",
        description="Pagination direction",
    )


class CursorPage(BaseModel, Generic[T]):
    """Standardized response schema for cursor-paginated datasets."""

    items: List[T]
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None
    has_more: bool = False
    total_count: Optional[int] = None

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]


def encode_cursor(payload: Dict[str, Any]) -> str:
    """Encode dictionary into base64 URL-safe opaque cursor string."""
    json_bytes = json.dumps(payload, default=str).encode("utf-8")
    return base64.urlsafe_b64encode(json_bytes).decode("utf-8")


def decode_cursor(cursor: Optional[str]) -> Optional[Dict[str, Any]]:
    """Decode base64 URL-safe opaque cursor string back into dictionary."""
    if not cursor:
        return None
    try:
        json_bytes = base64.urlsafe_b64decode(cursor.encode("utf-8"))
        return json.loads(json_bytes.decode("utf-8"))
    except Exception:
        return None
