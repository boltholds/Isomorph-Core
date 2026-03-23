import uuid
from collections import deque
from typing import Any

from isomorph_core.actions.registry import ActionRegistry
from isomorph_core.compiler.planner import ExecutionPlan, ExecutionNode
from isomorph_core.events.models import RuntimeEvent
from isomorph_core.events.runtime_bus import InMemoryRuntimeBus
from isomorph_core.operators.action import ActionOperator
from isomorph_core.operators.branch import BranchOperator
from isomorph_core.operators.foreach import ForeachOperator
from isomorph_core.operators.join import JoinOperator
from isomorph_core.operators.registry import OperatorRegistry
from isomorph_core.runtime.node_state import NodeRunState
from isomorph_core.runtime.state import ExecutionState
from isomorph_core.runtime.token import ExecutionToken


class WorkflowRuntime:
    def __init__(
        self,
        action_registry: ActionRegistry,
        runtime_bus: InMemoryRuntimeBus | None = None,
        operator_registry: OperatorRegistry | None = None,
    ) -> None:
        self._action_registry = action_registry
        self._runtime_bus = runtime_bus or InMemoryRuntimeBus()
        self._operator_registry = operator_registry or self._build_default_operator_registry()

    def _build_default_operator_registry(self) -> OperatorRegistry:
        registry = OperatorRegistry()
        registry.register("action", ActionOperator(self._action_registry))
        registry.register("branch", BranchOperator())
        registry.register("foreach", ForeachOperator())
        registry.register("join", JoinOperator())
        return registry

    async def run(self, plan: ExecutionPlan, inputs: dict[str, Any]) -> dict[str, Any]:
        execution_id = str(uuid.uuid4())

        state = ExecutionState(
            execution_id=execution_id,
            workflow_id=plan.workflow_id,
            node_states={
                node_id: NodeRunState(node_id=node_id)
                for node_id in plan.nodes
            },
            input_buffers={ node_id: {} for node_id in plan.nodes},
        )

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
            node_state = state.node_states[node.id]

            if node.kind == "join" and node_state.status == "done":
                continue

            if token.source_node_id is not None:
                self._buffer_input(
                    state=state,
                    target_node_id=node.id,
                    source_node_id=token.source_node_id,
                    payload=token.payload,
                )

            ready, prepared_inputs = self._prepare_inputs(
                node=node,
                token=token,
                state=state,
            )

            if not ready:
                node_state.status = "waiting"
                continue

            node_state.status = "running"

            await self._runtime_bus.publish(
                RuntimeEvent(
                    type="node_started",
                    execution_id=execution_id,
                    node_id=node.id,
                )
            )

            exec_token = token.model_copy(update={"payload": prepared_inputs})

            operator = self._operator_registry.resolve(node.kind)
            result = await operator.execute(node, exec_token)

            if result.status == "error":
                node_state.status = "failed"
                state.failed = True

                await self._runtime_bus.publish(
                    RuntimeEvent(
                        type="node_failed",
                        execution_id=execution_id,
                        node_id=node.id,
                        payload={"error": result.error},
                    )
                )
                raise RuntimeError(result.error or f"Node {node.id} failed")

            if node.kind == "join":
                state.input_buffers[node.id].clear()

            node_state.status = "done"
            last_outputs = result.outputs

            await self._runtime_bus.publish(
                RuntimeEvent(
                    type="node_completed",
                    execution_id=execution_id,
                    node_id=node.id,
                    payload=result.outputs,
                )
            )

            self._schedule_successors(
                queue=queue,
                node=node,
                token=token,
                result_outputs=result.outputs,
                execution_id=execution_id,
            )

        state.completed = True

        await self._runtime_bus.publish(
            RuntimeEvent(type="workflow_completed", execution_id=execution_id)
        )
        return last_outputs

    def _schedule_successors(
        self,
        *,
        queue: deque[ExecutionToken],
        node: ExecutionNode,
        token: ExecutionToken,
        result_outputs: dict[str, Any],
        execution_id: str,
    ) -> None:
        if node.kind == "foreach":
            items = result_outputs.get("__foreach_items__", [])
            group_id = str(uuid.uuid4())
            total = len(items)

            for nxt in node.outgoing:
                for index, item in enumerate(items):
                    child_payload = dict(token.payload)
                    child_payload["item"] = item
                    child_payload["__foreach__"] = {
                        "group_id": group_id,
                        "index": index,
                        "total": total,
                        "parent_node_id": node.id,
                    }

                    queue.append(
                        ExecutionToken(
                            execution_id=execution_id,
                            current_node_id=nxt,
                            source_node_id=node.id,
                            payload=child_payload,
                            parent_token_id=token.token_id,
                            foreach_group_id=group_id,
                            foreach_index=index,
                            foreach_total=total,
                        )
                    )
            return

        for nxt in node.outgoing:
            queue.append(
                ExecutionToken(
                    execution_id=execution_id,
                    current_node_id=nxt,
                    source_node_id=node.id,
                    payload=dict(result_outputs),
                    parent_token_id=token.token_id,
                    foreach_group_id=token.foreach_group_id,
                    foreach_index=token.foreach_index,
                    foreach_total=token.foreach_total,
                )
            )

    def _buffer_input(
        self,
        *,
        state: ExecutionState,
        target_node_id: str,
        source_node_id: str,
        payload: dict[str, Any],
    ) -> None:
        state.input_buffers.setdefault(target_node_id, {})
        state.input_buffers[target_node_id][source_node_id] = dict(payload)

    def _prepare_inputs(
        self,
        *,
        node: ExecutionNode,
        token: ExecutionToken,
        state: ExecutionState,
    ) -> tuple[bool, dict[str, Any]]:
        if not node.incoming:
            return True, dict(token.payload)

        if node.kind != "join":
            return True, dict(token.payload)

        join_mode = node.config.get("join_mode", "all")
        buffered_inputs = state.input_buffers.get(node.id, {})

        if join_mode == "all":
            missing_sources = [
                upstream_node_id
                for upstream_node_id in node.incoming
                if upstream_node_id not in buffered_inputs
            ]

            if missing_sources:
                return False, {}

            merged_inputs: dict[str, Any] = {}
            inputs_by_node: dict[str, dict[str, Any]] = {}

            for upstream_node_id in node.incoming:
                upstream_payload = dict(buffered_inputs[upstream_node_id])
                inputs_by_node[upstream_node_id] = upstream_payload
                merged_inputs.update(upstream_payload)

            merged_inputs["__inputs_by_node__"] = inputs_by_node
            return True, merged_inputs

        if join_mode == "any":
            if not buffered_inputs:
                return False, {}

            first_ready_source = next(iter(buffered_inputs))
            first_payload = dict(buffered_inputs[first_ready_source])

            first_payload["__inputs_by_node__"] = {
                first_ready_source: dict(buffered_inputs[first_ready_source])
            }
            first_payload["__join_triggered_by__"] = first_ready_source
            return True, first_payload

        raise NotImplementedError(f"Join mode '{join_mode}' is not implemented yet.")