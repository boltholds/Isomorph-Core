from typing import Literal
from pydantic import BaseModel


class NodeRunState(BaseModel):
    node_id: str
    status: Literal["idle", "waiting", "running", "done", "failed", "skipped"] = "idle"
    attempts: int = 0
