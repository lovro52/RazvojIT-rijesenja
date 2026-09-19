from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.logs import router as logs_router
from app.services.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Priprema baze pri dizanju poslužitelja.

    Zamjenjuje `@app.on_event("startup")`, koji je u novijim verzijama
    FastAPI-ja označen kao zastario i planiran za uklanjanje.
    """
    init_db()
    yield


app = FastAPI(
    title="NetlogRAG",
    version="1.0.0",
    description=(
        "Lokalna analiza mrežnih sigurnosnih zapisa. Klasifikacija pojedinog "
        "toka fine-tunanim modelom i sigurnosni izvještaji nad indeksiranim "
        "zapisima, bez slanja podataka izvan računala."
    ),
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(logs_router, prefix="/logs", tags=["logs"])
