from isomorph_core.actions.context import ActionContext
from isomorph_core.actions.result import ActionResult
from isomorph_core.compiler.planner import ExecutionNode
from isomorph_core.runtime.token import ExecutionToken


class ActionOperator:
    def __init__(self, registry, services: dict | None = None) -> None:
        self._registry = registry
        self._services = services or {}

    async def execute(self, node: ExecutionNode, token: ExecutionToken) -> ActionResult:
        action_name = node.ref
        if not action_name:
            return ActionResult(status="error", error=f"Node {node.id} has no action ref")

        action_cls = self._registry.resolve(action_name)
        action = action_cls()
        ctx = ActionContext(
            execution_id=token.execution_id,
            node_id=node.id,
            services=self._services,
        )
        return await action.run(token.payload, ctx, node.config)
