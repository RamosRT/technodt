from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.exceptions import AppError, app_error_handler
from app.routers.api import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # OData client and other long-lived resources will be wired in later tasks.
    yield


app = FastAPI(title="Конверт-трек", lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)
app.include_router(health.router)
