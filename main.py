from fastapi import FastAPI
from app.api.logs import router as logs_router
from app.services.database import init_db

app = FastAPI(
    title="RAG Security Log Analyzer",
    version="0.1.0",
    description="Upload network logs, index them semantically, and query with a local LLM.",
)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(logs_router, prefix="/logs", tags=["logs"])