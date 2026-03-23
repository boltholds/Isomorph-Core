from typing import Any, Literal
from pydantic import BaseModel, Field


class ActionResult(BaseModel):
    status: Literal["success", "error", "skipped"] = "success"
    outputs: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    error: str | None = None