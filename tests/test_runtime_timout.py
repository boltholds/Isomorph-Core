import asyncio
import pytest


from isomorph_core.actions.registry import ActionRegistry
from isomorph_core.actions.result import ActionResult
from isomorph_core.compiler.planner import WorkflowPlanner
from isomorph_core.definitions.node import NodeDefinition
from isomorph_core.definitions.workflow import WorkflowDefinition
from isomorph_core.runtime.engine import WorkflowRuntime


class SlowAction:
    async def run(self, inputs, ctx, config):
        await asyncio.sleep(0.2)
        return ActionResult(outputs={"ok": True})

@pytest.mark.asyncio
async def test_runtime_timeout_fails():
    registry = ActionRegistry()
    registry.register("slow", SlowAction)

    workflow = WorkflowDefinition(
        id="timeout_workflow",
        nodes=[
            NodeDefinition(
                id="n1",
                kind="action",
                ref="slow",
                policy={"timeout_seconds": 0.05},
            )
        ],
    )

    plan = WorkflowPlanner().build(workflow)
    runtime = WorkflowRuntime(registry)

    result = await runtime.run(plan, {})

    assert result.success is False
    assert "timed out" in (result.error or "")