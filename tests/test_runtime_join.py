import asyncio
import pytest



from isomorph_core.actions.result import ActionResult
from isomorph_core.actions.registry import ActionRegistry
from isomorph_core.compiler.planner import WorkflowPlanner
from isomorph_core.definitions.edge import EdgeDefinition
from isomorph_core.definitions.node import NodeDefinition
from isomorph_core.definitions.ports import PortRef
from isomorph_core.definitions.workflow import WorkflowDefinition
from isomorph_core.events.runtime_bus import InMemoryRuntimeBus
from isomorph_core.runtime.engine import WorkflowRuntime


class EmitLeftAction:
    async def run(self, inputs, ctx, config):
        return ActionResult(outputs={"a": 10})


class EmitRightAction:
    async def run(self, inputs, ctx, config):
        return ActionResult(outputs={"b": 32})


class SumAction:
    async def run(self, inputs, ctx, config):
        return ActionResult(outputs={"total": inputs["a"] + inputs["b"]})


@pytest.mark.asyncio
async def test_runtime_join_all_waits_for_all_upstreams():
    registry = ActionRegistry()
    registry.register("emit_left", EmitLeftAction)
    registry.register("emit_right", EmitRightAction)
    registry.register("sum", SumAction)

    workflow = WorkflowDefinition(
        id="join_workflow",
        nodes=[
            NodeDefinition(id="left", kind="action", ref="emit_left"),
            NodeDefinition(id="right", kind="action", ref="emit_right"),
            NodeDefinition(
                id="join",
                kind="join",
                config={"join_mode": "all"},
            ),
            NodeDefinition(id="sum", kind="action", ref="sum"),
        ],
        edges=[
            EdgeDefinition(
                source=PortRef(node_id="left", port="out"),
                target=PortRef(node_id="join", port="in"),
            ),
            EdgeDefinition(
                source=PortRef(node_id="right", port="out"),
                target=PortRef(node_id="join", port="in"),
            ),
            EdgeDefinition(
                source=PortRef(node_id="join", port="out"),
                target=PortRef(node_id="sum", port="in"),
            ),
        ],
    )

    plan = WorkflowPlanner().build(workflow)

    runtime_bus = InMemoryRuntimeBus()
    runtime = WorkflowRuntime(registry, runtime_bus=runtime_bus)

    result = await runtime.run(plan, {})

    assert result["total"] == 42

    join_started_events = [
        event for event in runtime_bus.events
        if event.type == "node_started" and event.node_id == "join"
    ]
    assert len(join_started_events) == 1