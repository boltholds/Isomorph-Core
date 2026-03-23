import asyncio
import uuid
from collections import deque
from typing import Any

from isomorph_core.actions.registry import ActionRegistry
from isomorph_core.compiler.planner import ExecutionNode, ExecutionPlan
from isomorph_core.events.models import RuntimeEvent
from isomorph_core.events.runtime_bus import InMemoryRuntimeBus
from isomorph_core.operators.action import ActionOperator
from isomorph_core.operators.branch import BranchOperator
from isomorph_core.operators.context import OperatorContext
from isomorph_core.operators.foreach import ForeachOperator
from isomorph_core.operators.join import JoinOperator
from isomorph_core.operators.registry import OperatorRegistry
from isomorph_core.runtime.node_state import NodeRunState
from isomorph_core.runtime.result import ExecutionResult
from isomorph_core.runtime.state import ExecutionState
from isomorph_core.runtime.token import ExecutionToken
from isomorph_core.actions.result import ActionResult

class WorkflowRuntime:
    def __init__(
        self,
        action_registry: ActionRegistry,
        runtime_bus: InMemoryRuntimeBus | None = None,
        operator_registry: OperatorRegistry | None = None,
        services: dict[str, Any] | None = None,
    ) -> None:
        self._action_registry = action_registry
        self._runtime_bus = runtime_bus or InMemoryRuntimeBus()
        self._services = services or {}
        self._operator_registry = operator_registry or self._build_default_operator_registry()

    def _build_default_operator_registry(self) -> OperatorRegistry:
        registry = OperatorRegistry()
        registry.register("action", ActionOperator(self._action_registry, services=self._services))
        registry.register("branch", BranchOperator())
        registry.register("foreach", ForeachOperator())
        registry.register("join", JoinOperator())
        return registry

    async def run(self, plan: ExecutionPlan, inputs: dict[str, Any]) -> ExecutionResult:
        execution_id = str(uuid.uuid4())

        state = ExecutionState(
            execution_id=execution_id,
            workflow_id=plan.workflow_id,
            node_states={node_id: NodeRunState(node_id=node_id) for node_id in plan.nodes},
            input_buffers={node_id: {} for node_id in plan.nodes},
            collect_buffers={node_id: {} for node_id in plan.nodes},
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

        await self._publish(RuntimeEvent(type="workflow_started", execution_id=execution_id))

        try:
            while queue:
                token = queue.popleft()
                node = plan.nodes[token.current_node_id]
                node_state = state.node_states[node.id]

                if node.kind == "join" and node_state.status == "done":
                    continue

                if token.source_node_id is not None:
                    self._buffer_input(
                        state=state,
                        node=node,
                        token=token,
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

                await self._publish(
                    RuntimeEvent(
                        type="node_started",
                        execution_id=execution_id,
                        node_id=node.id,
                    )
                )

                operator_ctx = OperatorContext(
                    execution_id=execution_id,
                    workflow_id=plan.workflow_id,
                    node_id=node.id,
                    services=self._services,
                    runtime_bus=self._runtime_bus,
                )

                exec_token = token.model_copy(update={"payload": prepared_inputs})
                result = await self._execute_with_policies(
                    node=node,
                    token=exec_token,
                    ctx=operator_ctx,
                    state=state,
                )

                if result.status == "error":
                    node_state.status = "failed"
                    state.failed = True

                    await self._publish(
                        RuntimeEvent(
                            type="node_failed",
                            execution_id=execution_id,
                            node_id=node.id,
                            payload={"error": result.error},
                        )
                    )

                    return ExecutionResult(
                        execution_id=execution_id,
                        workflow_id=plan.workflow_id,
                        success=False,
                        outputs={},
                        error=result.error,
                        failed_node_id=node.id,
                        runtime_events=list(self._runtime_bus.events),
                    )

                if node.kind == "join":
                    self._clear_join_buffers(state=state, node=node, token=token)

                node_state.status = "done"
                last_outputs = result.outputs

                await self._publish(
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

            await self._publish(
                RuntimeEvent(type="workflow_completed", execution_id=execution_id)
            )

            return ExecutionResult(
                execution_id=execution_id,
                workflow_id=plan.workflow_id,
                success=True,
                outputs=last_outputs,
                runtime_events=list(self._runtime_bus.events),
            )

        except Exception as exc:
            await self._publish(
                RuntimeEvent(
                    type="workflow_completed",
                    execution_id=execution_id,
                    payload={"unexpected_error": str(exc)},
                )
            )
            return ExecutionResult(
                execution_id=execution_id,
                workflow_id=plan.workflow_id,
                success=False,
                outputs={},
                error=str(exc),
                runtime_events=list(self._runtime_bus.events),
            )

    async def _execute_with_policies(
        self,
        *,
        node: ExecutionNode,
        token: ExecutionToken,
        ctx: OperatorContext,
        state: ExecutionState,
    ):
        operator = self._operator_registry.resolve(node.kind)

        retry_count = int(node.policy.get("retry_count", 0))
        timeout_seconds = node.policy.get("timeout_seconds")

        attempts = 0
        last_error: str | None = None

        while attempts <= retry_count:
            attempts += 1
            state.node_states[node.id].attempts = attempts

            try:
                if timeout_seconds is None:
                    return await operator.execute(node, token, ctx)

                return await asyncio.wait_for(
                    operator.execute(node, token, ctx),
                    timeout=float(timeout_seconds),
                )

            except asyncio.TimeoutError:
                last_error = f"Node '{node.id}' timed out after {timeout_seconds} seconds"

            except Exception as exc:
                last_error = str(exc)

            if attempts <= retry_count:
                await self._publish(
                    RuntimeEvent(
                        type="node_started",
                        execution_id=ctx.execution_id,
                        node_id=node.id,
                        payload={"retry_attempt": attempts},
                    )
                )

        
        return ActionResult(status="error", error=last_error or f"Node '{node.id}' failed")

    def _buffer_input(
        self,
        *,
        state: ExecutionState,
        node: ExecutionNode,
        token: ExecutionToken,
    ) -> None:
        if node.kind == "join" and node.config.get("join_mode") == "collect":
            group_id = token.foreach_group_id
            index = token.foreach_index

            if group_id is None or index is None:
                raise ValueError(
                    f"Join collect node '{node.id}' requires foreach_group_id and foreach_index"
                )

            state.collect_buffers.setdefault(node.id, {})
            state.collect_buffers[node.id].setdefault(group_id, {})
            state.collect_buffers[node.id][group_id][index] = dict(token.payload)
            return

        state.input_buffers.setdefault(node.id, {})
        if token.source_node_id is None:
            raise ValueError("source_node_id is required for buffered non-start input")
        state.input_buffers[node.id][token.source_node_id] = dict(token.payload)

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

        if join_mode == "collect":
            group_id = token.foreach_group_id
            total = token.foreach_total

            if group_id is None or total is None:
                return False, {}

            group_buffer = state.collect_buffers.get(node.id, {}).get(group_id, {})
            if len(group_buffer) < total:
                return False, {}

            ordered_items = [group_buffer[idx] for idx in sorted(group_buffer)]
            return True, {
                "items": ordered_items,
                "__collect__": {
                    "group_id": group_id,
                    "total": total,
                },
            }

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

    def _clear_join_buffers(
        self,
        *,
        state: ExecutionState,
        node: ExecutionNode,
        token: ExecutionToken,
    ) -> None:
        join_mode = node.config.get("join_mode", "all")

        if join_mode == "collect":
            group_id = token.foreach_group_id
            if group_id is not None:
                state.collect_buffers.get(node.id, {}).pop(group_id, None)
            return

        state.input_buffers[node.id].clear()

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

    async def _publish(self, event: RuntimeEvent) -> None:
        await self._runtime_bus.publish(event)