from typing import Any
from pydantic import BaseModel, Field

from isomorph_core.events.models import RuntimeEvent


class ExecutionResult(BaseModel):
    execution_id: str
    workflow_id: str
    success: bool
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    failed_node_id: str | None = None
    runtime_events: list[RuntimeEvent] = Field(default_factory=list)