from pydantic import BaseModel, Field
from typing import Any
import uuid


class ExecutionToken(BaseModel):
    token_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str
    current_node_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    parent_token_id: str | None = None
