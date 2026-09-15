from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.logs import router as logs_router
from app.services.database import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="NetlogRAG",
    version="0.2.0",
    description=(
        "Local network-flow analysis prototype. It aggregates flows into evidence "
        "windows and uses a local LLM to assist, not replace, a security analyst."
    ),
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}


app.include_router(logs_router, prefix="/logs", tags=["logs"])
