from typing import Literal

from pydantic import BaseModel, Field


class PrinterOut(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: Literal["zpl", "a4"]
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    dpi: int | None = None


class PrinterListResponse(BaseModel):
    items: list[PrinterOut]
