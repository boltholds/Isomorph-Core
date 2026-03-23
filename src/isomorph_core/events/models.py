from typing import Any, Literal
from pydantic import BaseModel, Field


class RuntimeEvent(BaseModel):
    type: Literal[
        "workflow_started",
        "workflow_completed",
        "node_started",
        "node_completed",
        "node_failed",
    ]
    execution_id: str
    node_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
