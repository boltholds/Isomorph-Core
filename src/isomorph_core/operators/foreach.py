from isomorph_core.actions.result import ActionResult
from isomorph_core.compiler.planner import ExecutionNode
from isomorph_core.runtime.token import ExecutionToken


class ForeachOperator:
    async def execute(self, node: ExecutionNode, token: ExecutionToken) -> ActionResult:
        items = token.payload.get("items", [])
        return ActionResult(outputs={"items": items})
