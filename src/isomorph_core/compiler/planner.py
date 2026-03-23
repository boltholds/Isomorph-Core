from pydantic import BaseModel, Field
from isomorph_core.definitions.workflow import WorkflowDefinition


class ExecutionNode(BaseModel):
    id: str
    kind: str
    ref: str | None = None
    incoming: list[str] = Field(default_factory=list)
    outgoing: list[str] = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    policy: dict = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    workflow_id: str
    nodes: dict[str, ExecutionNode]
    start_nodes: list[str]


class WorkflowPlanner:
    def build(self, workflow: WorkflowDefinition) -> ExecutionPlan:
        nodes = {
            node.id: ExecutionNode(
                id=node.id,
                kind=node.kind,
                ref=node.ref,
                config=node.config,
                policy=node.policy,
            )
            for node in workflow.nodes
        }

        for edge in workflow.edges:
            src = edge.source.node_id
            dst = edge.target.node_id
            nodes[src].outgoing.append(dst)
            nodes[dst].incoming.append(src)

        start_nodes = [node_id for node_id, node in nodes.items() if not node.incoming]
        return ExecutionPlan(workflow_id=workflow.id, nodes=nodes, start_nodes=start_nodes)
