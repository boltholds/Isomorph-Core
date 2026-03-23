from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ActionContext:
    execution_id: str
    node_id: str
    services: dict[str, Any] = field(default_factory=dict)
    cancellation_requested: bool = False
