import asyncio
import pytest


from isomorph_core.actions.registry import ActionRegistry
from isomorph_core.actions.result import ActionResult
from isomorph_core.compiler.planner import WorkflowPlanner
from isomorph_core.definitions.node import NodeDefinition
from isomorph_core.definitions.workflow import WorkflowDefinition
from isomorph_core.runtime.engine import WorkflowRuntime


class FlakyAction:
    def __init__(self):
        if not hasattr(self.__class__, "_attempts"):
            self.__class__._attempts = 0

    async def run(self, inputs, ctx, config):
        self.__class__._attempts += 1
        if self.__class__._attempts < 3:
            raise RuntimeError("temporary error")
        return ActionResult(outputs={"ok": True})

@pytest.mark.asyncio
async def test_runtime_retry_succeeds():
    FlakyAction._attempts = 0

    registry = ActionRegistry()
    registry.register("flaky", FlakyAction)

    workflow = WorkflowDefinition(
        id="retry_workflow",
        nodes=[
            NodeDefinition(
                id="n1",
                kind="action",
                ref="flaky",
                policy={"retry_count": 2},
            )
        ],
    )

    plan = WorkflowPlanner().build(workflow)
    runtime = WorkflowRuntime(registry)

    result = await runtime.run(plan, {})

    assert result.success is True
    assert result.outputs["ok"] is True