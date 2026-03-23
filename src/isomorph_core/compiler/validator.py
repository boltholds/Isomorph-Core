from isomorph_core.definitions.workflow import WorkflowDefinition


class WorkflowValidationError(ValueError):
    pass


class WorkflowValidator:
    def validate(self, workflow: WorkflowDefinition) -> None:
        node_ids = [node.id for node in workflow.nodes]
        unique_ids = set(node_ids)

        if len(node_ids) != len(unique_ids):
            raise WorkflowValidationError("Node ids must be unique.")

        for edge in workflow.edges:
            if edge.source.node_id not in unique_ids:
                raise WorkflowValidationError(
                    f"Unknown source node: {edge.source.node_id}"
                )
            if edge.target.node_id not in unique_ids:
                raise WorkflowValidationError(
                    f"Unknown target node: {edge.target.node_id}"
                )
