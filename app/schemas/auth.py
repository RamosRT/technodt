from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class LoginResponse(BaseModel):
    ok: bool
    operator: str


class MeResponse(BaseModel):
    operator: str
    is_admin: bool
