import pytest

from isomorph_core.compiler.validator import WorkflowValidationError, WorkflowValidator
from isomorph_core.definitions.edge import EdgeDefinition
from isomorph_core.definitions.node import NodeDefinition
from isomorph_core.definitions.ports import PortRef
from isomorph_core.definitions.workflow import WorkflowDefinition


def test_validator_rejects_cycle():
    workflow = WorkflowDefinition(
        id="cyclic",
        nodes=[
            NodeDefinition(id="a", kind="action", ref="x"),
            NodeDefinition(id="b", kind="action", ref="y"),
        ],
        edges=[
            EdgeDefinition(
                source=PortRef(node_id="a", port="out"),
                target=PortRef(node_id="b", port="in"),
            ),
            EdgeDefinition(
                source=PortRef(node_id="b", port="out"),
                target=PortRef(node_id="a", port="in"),
            ),
        ],
    )

    validator = WorkflowValidator()

    with pytest.raises(WorkflowValidationError, match="Cycle detected"):
        validator.validate(workflow)

