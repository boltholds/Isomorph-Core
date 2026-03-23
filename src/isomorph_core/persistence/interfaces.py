from typing import Protocol
from isomorph_core.runtime.state import ExecutionState


class StateStore(Protocol):
    async def save(self, state: ExecutionState) -> None:
        ...

    async def load(self, execution_id: str) -> ExecutionState | None:
        ...
