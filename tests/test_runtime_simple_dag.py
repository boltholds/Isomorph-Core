from isomorph_core.actions.result import ActionResult
from isomorph_core.actions.registry import ActionRegistry
from isomorph_core.compiler.planner import WorkflowPlanner
from isomorph_core.definitions.edge import EdgeDefinition
from isomorph_core.definitions.node import NodeDefinition
from isomorph_core.definitions.ports import PortRef
from isomorph_core.definitions.workflow import WorkflowDefinition
from isomorph_core.runtime.engine import WorkflowRuntime


class AddOneAction:
    async def run(self, inputs, ctx, config):
        value = inputs.get("value", 0)
        return ActionResult(outputs={"value": value + 1})


async def test_runtime_simple_dag():
    registry = ActionRegistry()
    registry.register("add_one", AddOneAction)

    workflow = WorkflowDefinition(
        id="wf",
        nodes=[
            NodeDefinition(id="n1", kind="action", ref="add_one"),
            NodeDefinition(id="n2", kind="action", ref="add_one"),
        ],
        edges=[
            EdgeDefinition(
                source=PortRef(node_id="n1", port="out"),
                target=PortRef(node_id="n2", port="in"),
            )
        ],
    )

    plan = WorkflowPlanner().build(workflow)
    runtime = WorkflowRuntime(registry)

    result = await runtime.run(plan, {"value": 1})
    assert result["value"] == 3