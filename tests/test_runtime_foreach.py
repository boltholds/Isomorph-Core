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


class ProduceItemsAction:
    async def run(self, inputs, ctx, config):
        return ActionResult(outputs={"items": [1, 2, 3]})


class MultiplyByTwoAction:
    async def run(self, inputs, ctx, config):
        item = inputs["item"]
        meta = inputs["__foreach__"]
        return ActionResult(
            outputs={
                "value": item * 2,
                "index": meta["index"],
                "total": meta["total"],
            }
        )

@pytest.mark.asyncio
async def test_runtime_foreach_spawns_child_tokens():
    registry = ActionRegistry()
    registry.register("produce_items", ProduceItemsAction)
    registry.register("mul2", MultiplyByTwoAction)

    workflow = WorkflowDefinition(
        id="foreach_workflow",
        nodes=[
            NodeDefinition(id="produce", kind="action", ref="produce_items"),
            NodeDefinition(id="loop", kind="foreach"),
            NodeDefinition(id="worker", kind="action", ref="mul2"),
        ],
        edges=[
            EdgeDefinition(
                source=PortRef(node_id="produce", port="out"),
                target=PortRef(node_id="loop", port="in"),
            ),
            EdgeDefinition(
                source=PortRef(node_id="loop", port="out"),
                target=PortRef(node_id="worker", port="in"),
            ),
        ],
    )

    plan = WorkflowPlanner().build(workflow)

    runtime_bus = InMemoryRuntimeBus()
    runtime = WorkflowRuntime(registry, runtime_bus=runtime_bus)

    result = await runtime.run(plan, {})
    assert result.outputs["value"] in {2, 4, 6}
    assert result.outputs["total"] == 3

    worker_completed = [
        event for event in runtime_bus.events
        if event.type == "node_completed" and event.node_id == "worker"
    ]
    assert len(worker_completed) == 3
