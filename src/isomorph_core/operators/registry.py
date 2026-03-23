from isomorph_core.operators.base import Operator


class OperatorRegistry:
    def __init__(self) -> None:
        self._operators: dict[str, Operator] = {}

    def register(self, kind: str, operator: Operator) -> None:
        if kind in self._operators:
            raise ValueError(f"Operator already registered for kind: {kind}")
        self._operators[kind] = operator

    def resolve(self, kind: str) -> Operator:
        try:
            return self._operators[kind]
        except KeyError as exc:
            raise KeyError(f"Unknown operator kind: {kind}") from exc