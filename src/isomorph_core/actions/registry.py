from typing import Type
from isomorph_core.actions.contracts import Action


class ActionRegistry:
    def __init__(self) -> None:
        self._actions: dict[str, Type[Action]] = {}

    def register(self, name: str, action_cls: Type[Action]) -> None:
        if name in self._actions:
            raise ValueError(f"Action already registered: {name}")
        self._actions[name] = action_cls

    def resolve(self, name: str) -> Type[Action]:
        try:
            return self._actions[name]
        except KeyError as exc:
            raise KeyError(f"Unknown action: {name}") from exc
