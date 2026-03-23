from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class OperatorContext:
    execution_id: str
    workflow_id: str
    node_id: str
    services: dict[str, Any] = field(default_factory=dict)
    runtime_bus: Any | None = None
    domain_bus: Any | None = None
    state_store: Any | None = None