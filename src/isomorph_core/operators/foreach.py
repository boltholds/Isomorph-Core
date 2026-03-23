from isomorph_core.actions.result import ActionResult
from isomorph_core.compiler.planner import ExecutionNode
from isomorph_core.operators.context import OperatorContext
from isomorph_core.runtime.token import ExecutionToken


class ForeachOperator:
    async def execute(
        self,
        node: ExecutionNode,
        token: ExecutionToken,
        ctx: OperatorContext,
    ) -> ActionResult:
        input_key = node.config.get("input_key", "items")
        items = token.payload.get(input_key, [])

        if not isinstance(items, list):
            return ActionResult(
                status="error",
                error=f"Foreach node '{node.id}' expected list in '{input_key}'",
            )

        return ActionResult(
            outputs={
                "__foreach_items__": items,
                "__foreach_input_key__": input_key,
            }
        )
