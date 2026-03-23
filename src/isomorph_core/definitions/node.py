from typing import Any, Literal
from pydantic import BaseModel, Field


NodeKind = Literal["action", "branch", "foreach", "join"]


class NodeDefinition(BaseModel):
    id: str
    kind: NodeKind
    ref: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)