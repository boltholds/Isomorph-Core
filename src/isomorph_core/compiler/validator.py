from isomorph_core.definitions.workflow import WorkflowDefinition
from collections import defaultdict

class WorkflowValidationError(ValueError):
    pass


class WorkflowValidator:
    def validate(self, workflow: WorkflowDefinition) -> None:
        node_ids = [node.id for node in workflow.nodes]
        unique_ids = set(node_ids)

        if len(node_ids) != len(unique_ids):
            raise WorkflowValidationError("Node ids must be unique.")

        adjacency: dict[str, list[str]] = defaultdict(list)

        for edge in workflow.edges:
            if edge.source.node_id not in unique_ids:
                raise WorkflowValidationError(
                    f"Unknown source node: {edge.source.node_id}"
                )
            if edge.target.node_id not in unique_ids:
                raise WorkflowValidationError(
                    f"Unknown target node: {edge.target.node_id}"
                )
            adjacency[edge.source.node_id].append(edge.target.node_id)

        self._validate_acyclic_graph(node_ids=node_ids, adjacency=adjacency)

    def _validate_acyclic_graph(
        self,
        *,
        node_ids: list[str],
        adjacency: dict[str, list[str]],
    ) -> None:
        color: dict[str, int] = {node_id: 0 for node_id in node_ids}
        # 0 = unvisited, 1 = visiting, 2 = visited

        def dfs(node_id: str) -> None:
            color[node_id] = 1

            for next_node_id in adjacency.get(node_id, []):
                if color[next_node_id] == 1:
                    raise WorkflowValidationError(
                        f"Cycle detected involving node '{next_node_id}'"
                    )
                if color[next_node_id] == 0:
                    dfs(next_node_id)

            color[node_id] = 2

        for node_id in node_ids:
            if color[node_id] == 0:
                dfs(node_id)
