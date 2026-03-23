from isomorph_core.persistence.interfaces import StateStore
from isomorph_core.runtime.state import ExecutionState


class InMemoryStateStore(StateStore):
    def __init__(self) -> None:
        self._storage: dict[str, ExecutionState] = {}

    async def save(self, state: ExecutionState) -> None:
        self._storage[state.execution_id] = state

    async def load(self, execution_id: str) -> ExecutionState | None:
        return self._storage.get(execution_id)
