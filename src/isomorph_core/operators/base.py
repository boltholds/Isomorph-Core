from typing import Protocol

from isomorph_core.actions.result import ActionResult
from isomorph_core.compiler.planner import ExecutionNode
from isomorph_core.operators.context import OperatorContext
from isomorph_core.runtime.token import ExecutionToken


class Operator(Protocol):
    async def execute(
        self,
        node: ExecutionNode,
        token: ExecutionToken,
        ctx: OperatorContext,
    ) -> ActionResult:
        ...
