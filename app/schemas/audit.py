import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    envelope_id: uuid.UUID | None
    event: str
    payload: dict[str, Any]
    actor: str
    at: datetime
