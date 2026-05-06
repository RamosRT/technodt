from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")


class LoginResponse(BaseModel):
    ok: bool
    operator: str
    assigned_zpl_printer_id: str | None = None
    assigned_a4_printer_id: str | None = None


class MeResponse(BaseModel):
    operator: str
    is_admin: bool
