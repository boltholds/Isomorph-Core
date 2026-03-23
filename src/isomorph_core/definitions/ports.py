from pydantic import BaseModel


class PortRef(BaseModel):
    node_id: str
    port: str
