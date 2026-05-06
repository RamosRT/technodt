import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OperatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    is_admin: bool
    is_active: bool
    assigned_zpl_printer_id: str | None
    assigned_a4_printer_id: str | None
    default_branch_id: uuid.UUID | None
    default_signer_sender_id: uuid.UUID | None
    created_at: datetime


class OperatorCreate(BaseModel):
    username: str
    password: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    is_admin: bool = False
    assigned_zpl_printer_id: str | None = None
    assigned_a4_printer_id: str | None = None


class OperatorPatch(BaseModel):
    password: str | None = Field(default=None, min_length=4, max_length=4, pattern=r"^\d{4}$")
    is_admin: bool | None = None
    is_active: bool | None = None
    assigned_zpl_printer_id: str | None = None
    assigned_a4_printer_id: str | None = None
    default_branch_id: uuid.UUID | None = None
    default_signer_sender_id: uuid.UUID | None = None


class OperatorSettingsPatch(BaseModel):
    zpl_printer_id: str | None = None
    a4_printer_id: str | None = None
    default_branch_id: uuid.UUID | None = None
    default_signer_sender_id: uuid.UUID | None = None
