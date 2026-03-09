from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import Optional
import pandas as pd
from pathlib import Path
from datetime import datetime

from app.core.config import UPLOAD_DIR
from app.services.normalize import normalize_dataframe
from app.services.vector_store import index_records, semantic_search
from app.services.llm_local import generate_local_security_report
from app.services.database import (
    save_uploaded_file,
    save_log_records,
    mark_file_indexed,
    list_uploaded_files,
    filter_logs,
    get_dashboard_stats,
)

router = APIRouter()

_upload_dir = Path(UPLOAD_DIR)
_upload_dir.mkdir(parents=True, exist_ok=True)


# ── helpers ──────────────────────────────────────────────────────────────────

def _load_csv(filename: str) -> pd.DataFrame:
    path = _upload_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found in uploads.")
    try:
        return pd.read_csv(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}")


# ── routes ───────────────────────────────────────────────────────────────────

@router.post("/upload", summary="Upload a CSV log file")
async def upload_logs(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    ts        = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{ts}_{file.filename}".replace(" ", "_")
    save_path = _upload_dir / safe_name
    save_path.write_bytes(await file.read())

    df = _load_csv(safe_name)

    save_uploaded_file(
        filename    = safe_name,
        uploaded_at = datetime.utcnow().isoformat(),
        rows        = int(len(df)),
    )

    return {
        "message":  "uploaded",
        "filename": safe_name,
        "rows":     int(len(df)),
        "columns":  list(df.columns),
        "preview":  df.head(5).to_dict(orient="records"),
    }


@router.post("/normalize", summary="Normalize a previously uploaded CSV")
async def normalize_uploaded_csv(filename: str):
    df      = _load_csv(filename)
    records = normalize_dataframe(df)
    return {
        "filename":      filename,
        "records_count": len(records),
        "sample":        records[:5],
    }


@router.post("/index", summary="Normalize + embed + store a CSV into ChromaDB and SQLite")
async def index_uploaded_csv(filename: str):
    df      = _load_csv(filename)
    records = normalize_dataframe(df)

    # Index into vector store
    count = index_records(records, source_filename=filename)

    # Save to SQLite
    save_log_records(records, source_file=filename)
    mark_file_indexed(filename)

    return {
        "message":         "indexed",
        "filename":        filename,
        "indexed_records": count,
    }


@router.get("/dashboard", summary="Aggregated stats for the dashboard")
async def dashboard():
    return get_dashboard_stats()


@router.get("/files", summary="List all uploaded and indexed files")
async def get_uploaded_files():
    return {"files": list_uploaded_files()}


@router.get("/filter", summary="Filter log records by IP, time, protocol, action")
async def filter_log_records(
    src_ip:      Optional[str] = Query(None, description="Filter by source IP (partial match)"),
    dst_ip:      Optional[str] = Query(None, description="Filter by destination IP (partial match)"),
    hours:       Optional[int] = Query(None, description="Records from last N hours"),
    protocol:    Optional[str] = Query(None, description="Protocol (e.g. TCP, UDP)"),
    action:      Optional[str] = Query(None, description="Action/flag (e.g. SYN, PSH, ACK)"),
    source_file: Optional[str] = Query(None, description="Filter by source filename"),
):
    records = filter_logs(
        src_ip=src_ip,
        dst_ip=dst_ip,
        hours=hours,
        protocol=protocol,
        action=action,
        source_file=source_file,
    )
    return {
        "count":   len(records),
        "records": records,
    }


@router.get("/query/semantic", summary="Semantic search over indexed logs")
async def query_semantic(
    q:     str = Query(..., description="Natural-language query"),
    top_k: int = Query(5,   description="Number of results to return"),
):
    return semantic_search(query=q, top_k=top_k)


@router.get("/query/rag_local", summary="RAG query answered by local Ollama model")
async def query_rag_local(
    q:     str = Query(..., description="Security question to answer"),
    top_k: int = Query(5,   description="Evidence records to retrieve"),
):
    retrieved = semantic_search(query=q, top_k=top_k)["results"]
    report    = generate_local_security_report(query=q, evidence=retrieved)
    return {
        "query":    q,
        "top_k":    top_k,
        "report":   report,
        "evidence": retrieved,
    }