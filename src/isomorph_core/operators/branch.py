from isomorph_core.actions.result import ActionResult
from isomorph_core.compiler.planner import ExecutionNode
from isomorph_core.runtime.token import ExecutionToken
from isomorph_core.operators.context import OperatorContext



class BranchOperator:
    async def execute(
        self,
        node: ExecutionNode,
        token: ExecutionToken,
        ctx: OperatorContext,
    ) -> ActionResult:
        return ActionResult(outputs=token.payload)
