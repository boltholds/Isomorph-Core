import uuid
from collections import deque
from typing import Any

from isomorph_core.actions.registry import ActionRegistry
from isomorph_core.compiler.planner import ExecutionPlan
from isomorph_core.events.models import RuntimeEvent
from isomorph_core.events.runtime_bus import InMemoryRuntimeBus
from isomorph_core.operators.action import ActionOperator
from isomorph_core.operators.branch import BranchOperator
from isomorph_core.operators.foreach import ForeachOperator
from isomorph_core.operators.join import JoinOperator
from isomorph_core.runtime.token import ExecutionToken


class WorkflowRuntime:
    def __init__(
        self,
        action_registry: ActionRegistry,
        runtime_bus: InMemoryRuntimeBus | None = None,
    ) -> None:
        self._action_registry = action_registry
        self._runtime_bus = runtime_bus or InMemoryRuntimeBus()
        self._action_operator = ActionOperator(action_registry)
        self._branch_operator = BranchOperator()
        self._foreach_operator = ForeachOperator()
        self._join_operator = JoinOperator()

    async def run(self, plan: ExecutionPlan, inputs: dict[str, Any]) -> dict[str, Any]:
        execution_id = str(uuid.uuid4())
        queue = deque(
            ExecutionToken(
                execution_id=execution_id,
                current_node_id=node_id,
                payload=dict(inputs),
            )
            for node_id in plan.start_nodes
        )

        last_outputs: dict[str, Any] = {}

        await self._runtime_bus.publish(
            RuntimeEvent(type="workflow_started", execution_id=execution_id)
        )

        while queue:
            token = queue.popleft()
            node = plan.nodes[token.current_node_id]

            await self._runtime_bus.publish(
                RuntimeEvent(type="node_started", execution_id=execution_id, node_id=node.id)
            )

            if node.kind == "action":
                result = await self._action_operator.execute(node, token)
            elif node.kind == "branch":
                result = await self._branch_operator.execute(node, token)
            elif node.kind == "foreach":
                result = await self._foreach_operator.execute(node, token)
            elif node.kind == "join":
                result = await self._join_operator.execute(node, token)
            else:
                raise ValueError(f"Unsupported node kind: {node.kind}")

            if result.status == "error":
                await self._runtime_bus.publish(
                    RuntimeEvent(
                        type="node_failed",
                        execution_id=execution_id,
                        node_id=node.id,
                        payload={"error": result.error},
                    )
                )
                raise RuntimeError(result.error or f"Node {node.id} failed")

            last_outputs = result.outputs

            await self._runtime_bus.publish(
                RuntimeEvent(
                    type="node_completed",
                    execution_id=execution_id,
                    node_id=node.id,
                    payload=result.outputs,
                )
            )

            for nxt in node.outgoing:
                queue.append(
                    ExecutionToken(
                        execution_id=execution_id,
                        current_node_id=nxt,
                        payload=dict(result.outputs),
                        parent_token_id=token.token_id,
                    )
                )

        await self._runtime_bus.publish(
            RuntimeEvent(type="workflow_completed", execution_id=execution_id)
        )
        return last_outputs