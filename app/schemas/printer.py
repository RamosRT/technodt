from typing import Literal

from pydantic import BaseModel, Field


class PrinterOut(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: Literal["zpl", "a4"]
    is_active: bool = True
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    dpi: int | None = None
    share_name: str | None = None


class PrinterCreate(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["zpl", "a4"]
    is_active: bool = True
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    dpi: int | None = None
    share_name: str | None = None


class PrinterPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    kind: Literal["zpl", "a4"] | None = None
    is_active: bool | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    dpi: int | None = None
    share_name: str | None = None


class PrinterListResponse(BaseModel):
    items: list[PrinterOut]
