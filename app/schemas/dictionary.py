import uuid

from pydantic import BaseModel, ConfigDict, Field


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class BranchPatch(BaseModel):
    is_active: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)


class SignerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    last_name: str
    first_name: str
    is_active: bool


class SignerCreate(BaseModel):
    last_name: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)


class SignerPatch(BaseModel):
    is_active: bool | None = None
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
