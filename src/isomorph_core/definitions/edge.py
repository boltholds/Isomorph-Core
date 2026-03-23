from pydantic import BaseModel
from isomorph_core.definitions.ports import PortRef


class EdgeDefinition(BaseModel):
    source: PortRef
    target: PortRef
