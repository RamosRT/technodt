import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OperatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    is_admin: bool
    is_active: bool
    created_at: datetime


class OperatorCreate(BaseModel):
    username: str
    is_admin: bool = False


class OperatorPatch(BaseModel):
    is_admin: bool | None = None
    is_active: bool | None = None
