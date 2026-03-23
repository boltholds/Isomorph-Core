from typing import Protocol
from isomorph_core.compiler.planner import ExecutionNode
from isomorph_core.runtime.token import ExecutionToken
from isomorph_core.actions.result import ActionResult


class Operator(Protocol):
    async def execute(
        self,
        node: ExecutionNode,
        token: ExecutionToken,
    ) -> ActionResult:
        ...
