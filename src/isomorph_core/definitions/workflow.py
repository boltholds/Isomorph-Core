from pydantic import BaseModel, Field
from isomorph_core.definitions.node import NodeDefinition
from isomorph_core.definitions.edge import EdgeDefinition


class WorkflowDefinition(BaseModel):
    id: str
    version: str = "1.0"
    nodes: list[NodeDefinition] = Field(default_factory=list)
    edges: list[EdgeDefinition] = Field(default_factory=list)
