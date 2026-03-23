from typing import Protocol, Any
from isomorph_core.actions.context import ActionContext
from isomorph_core.actions.result import ActionResult


class Action(Protocol):
    async def run(
        self,
        inputs: dict[str, Any],
        ctx: ActionContext,
        config: dict[str, Any],
    ) -> ActionResult:
        ...
