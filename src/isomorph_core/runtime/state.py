from pydantic import BaseModel, Field
from isomorph_core.runtime.node_state import NodeRunState


class ExecutionState(BaseModel):
    execution_id: str
    workflow_id: str
    node_states: dict[str, NodeRunState] = Field(default_factory=dict)
    input_buffers: dict[str, list[dict]] = Field(default_factory=dict)
    completed: bool = False
    failed: bool = False
