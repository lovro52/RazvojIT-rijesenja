from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.core.config import (
    AVAILABLE_MODELS,
    FINE_TUNING_CANDIDATES,
    MAX_COMPARE_MODELS,
    MAX_QUERY_LENGTH,
    MAX_TOP_K,
    MAX_UPLOAD_BYTES,
    UPLOAD_DIR,
)
from app.services.baseline import (
    evaluate_on_file,
    get_baseline_status,
    predict_record,
    train_models,
)
from app.services.database import (
    filter_logs,
    get_dashboard_stats,
    get_ip_stats,
    get_query_history,
    keyword_search,
    list_all_ips,
    list_uploaded_files,
    mark_file_indexed,
    save_log_records,
    save_query,
    save_uploaded_file,
)
from app.services.llm_classifier import classify_flow
from app.services.llm_local import (
    DetectionMode,
    UnsupportedDetectionModeError,
    generate_local_security_report_mode,
)
from app.services.normalize import build_flow_incidents, normalize_dataframe
from app.services.vector_store import delete_source, index_records, semantic_search

router = APIRouter()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_CSV_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "text/plain",
    "application/octet-stream",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _resolve_upload(filename: str) -> Path:
    if not filename or Path(filename).name != filename:
        raise HTTPException(status_code=400, detail="Neispravan naziv datoteke.")
    candidate = (UPLOAD_DIR / filename).resolve()
    root = UPLOAD_DIR.resolve()
    if candidate.parent != root:
        raise HTTPException(status_code=400, detail="Neispravna putanja datoteke.")
    return candidate


def _load_csv(filename: str) -> pd.DataFrame:
    path = _resolve_upload(filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Datoteka nije pronađena.")
    try:
        return pd.read_csv(path)
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"CSV nije moguće pročitati: {exc}") from exc


def _json_preview(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    clean = dataframe.head(5).astype(object).where(pd.notna(dataframe.head(5)), None)
    return clean.to_dict(orient="records")


def _index_file(filename: str) -> tuple[int, int]:
    dataframe = _load_csv(filename)
    flows = normalize_dataframe(dataframe)
    incidents = build_flow_incidents(flows)
    indexed_count = index_records(incidents, source_filename=filename)
    try:
        save_log_records(flows, source_file=filename)
        mark_file_indexed(filename)
    except Exception:
        delete_source(filename)
        raise
    return len(flows), indexed_count


@router.post("/upload", summary="Učitaj CSV zapis mrežnog prometa")
async def upload_logs(file: UploadFile = File(...)):
    original = Path(file.filename or "").name
    if not original.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Prihvaćaju se samo CSV datoteke.")
    if file.content_type and file.content_type.lower() not in _CSV_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Nepodržana vrsta sadržaja datoteke.")

    normalized_name = _SAFE_NAME.sub("_", original).strip("._") or "logs.csv"
    stem = Path(normalized_name).stem[:100]
    stored_name = f"{datetime.now(UTC):%Y%m%d_%H%M%S_%f}_{uuid4().hex[:8]}_{stem}.csv"
    final_path = _resolve_upload(stored_name)
    temporary_path = final_path.with_suffix(".part")
    total = 0
    try:
        with temporary_path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Datoteka prelazi ograničenje od {MAX_UPLOAD_BYTES} bajtova.",
                    )
                if total <= 1024 * 1024 and b"\x00" in chunk:
                    raise HTTPException(status_code=400, detail="Datoteka nije tekstualni CSV.")
                destination.write(chunk)
        dataframe = await run_in_threadpool(pd.read_csv, temporary_path)
        temporary_path.replace(final_path)
    except HTTPException:
        temporary_path.unlink(missing_ok=True)
        raise
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError) as exc:
        temporary_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Neispravan CSV: {exc}") from exc
    finally:
        await file.close()

    try:
        await run_in_threadpool(save_uploaded_file, stored_name, _utc_now(), len(dataframe))
    except Exception:
        final_path.unlink(missing_ok=True)
        raise
    return {
        "message": "uploaded",
        "filename": stored_name,
        "original_filename": original,
        "size_bytes": total,
        "rows": int(len(dataframe)),
        "columns": [str(column) for column in dataframe.columns],
        "preview": _json_preview(dataframe),
    }


@router.post("/normalize", summary="Normaliziraj prethodno učitani CSV")
async def normalize_uploaded_csv(filename: Annotated[str, Query(min_length=1, max_length=180)]):
    dataframe = await run_in_threadpool(_load_csv, filename)
    records = await run_in_threadpool(normalize_dataframe, dataframe)
    return {"filename": filename, "records_count": len(records), "sample": records[:5]}


@router.post("/index", summary="Normaliziraj, agregiraj i indeksiraj CSV")
async def index_uploaded_csv(
    filename: Annotated[str, Query(min_length=1, max_length=180)],
    auto_analyze: bool = True,
):
    flow_count, incident_count = await run_in_threadpool(_index_file, filename)
    auto_report = None
    auto_error = None
    if auto_analyze and incident_count:
        query = "Analiziraj agregirane sigurnosne obrasce u ovoj datoteci."
        try:
            search = await run_in_threadpool(
                semantic_search, query, min(10, incident_count), filename
            )
            evidence = search["results"]
            auto_report = await run_in_threadpool(
                generate_local_security_report_mode, query, evidence, None, "flow"
            )
            await run_in_threadpool(
                save_query,
                query,
                min(10, incident_count),
                auto_report,
                len(evidence),
                _utc_now(),
                auto_report.get("model_used"),
                "flow",
                filename,
                [item["id"] for item in evidence],
                auto_report.get("prompt_version"),
            )
        except Exception as exc:
            auto_error = str(exc)
    return {
        "message": "indexed",
        "filename": filename,
        "normalized_flows": flow_count,
        "indexed_incidents": incident_count,
        "auto_report": auto_report,
        "auto_analysis_error": auto_error,
    }


@router.get("/dashboard")
async def dashboard():
    return await run_in_threadpool(get_dashboard_stats)


@router.get("/files")
async def get_uploaded_files():
    return {"files": await run_in_threadpool(list_uploaded_files)}


@router.get("/filter")
async def filter_log_records(
    src_ip: str | None = Query(None, max_length=64),
    dst_ip: str | None = Query(None, max_length=64),
    hours: int | None = Query(None, ge=1, le=24 * 366),
    protocol: str | None = Query(None, max_length=20),
    action: str | None = Query(None, max_length=40),
    source_file: str | None = Query(None, max_length=180),
):
    records = await run_in_threadpool(
        filter_logs, src_ip, dst_ip, hours, protocol, action, source_file
    )
    return {"count": len(records), "records": records}


@router.get("/query/semantic")
async def query_semantic(
    q: str = Query(..., min_length=2, max_length=MAX_QUERY_LENGTH),
    top_k: int = Query(5, ge=1, le=MAX_TOP_K),
    source_file: str | None = Query(None, max_length=180),
):
    return await run_in_threadpool(semantic_search, q, top_k, source_file)


@router.get("/query/rag_local")
async def query_rag_local(
    q: str = Query(..., min_length=2, max_length=MAX_QUERY_LENGTH),
    top_k: int = Query(5, ge=1, le=MAX_TOP_K),
    model: str | None = Query(None, max_length=100),
    source_file: str | None = Query(None, max_length=180),
):
    return await query_rag_local_mode(q, top_k, model, DetectionMode.FLOW, source_file)


@router.get("/query/rag_local_mode")
async def query_rag_local_mode(
    q: str = Query(..., min_length=2, max_length=MAX_QUERY_LENGTH),
    top_k: int = Query(5, ge=1, le=MAX_TOP_K),
    model: str | None = Query(None, max_length=100),
    mode: DetectionMode = Query(DetectionMode.AUTO),
    source_file: str | None = Query(None, max_length=180),
):
    search = await run_in_threadpool(semantic_search, q, top_k, source_file)
    evidence = search["results"]
    try:
        report = await run_in_threadpool(
            generate_local_security_report_mode, q, evidence, model, mode.value
        )
    except UnsupportedDetectionModeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await run_in_threadpool(
        save_query,
        q,
        top_k,
        report,
        len(evidence),
        _utc_now(),
        report.get("model_used"),
        report.get("detection_mode"),
        source_file,
        [item["id"] for item in evidence],
        report.get("prompt_version"),
    )
    return {
        "query": q,
        "top_k": top_k,
        "source_file": source_file,
        "mode": report.get("detection_mode"),
        "model": report.get("model_used"),
        "report": report,
        "evidence": evidence,
    }


@router.get("/models")
async def list_models():
    return {
        "models": AVAILABLE_MODELS,
        "fine_tuning_candidates": FINE_TUNING_CANDIDATES,
    }


@router.get("/query/compare_models")
async def compare_models(
    q: str = Query(..., min_length=2, max_length=MAX_QUERY_LENGTH),
    top_k: int = Query(5, ge=1, le=MAX_TOP_K),
    models: str = Query("llama3.1:8b", max_length=400),
    source_file: str | None = Query(None, max_length=180),
):
    model_list = list(dict.fromkeys(item.strip() for item in models.split(",") if item.strip()))
    if not model_list or len(model_list) > MAX_COMPARE_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Odaberi između 1 i {MAX_COMPARE_MODELS} modela.",
        )
    evidence = (await run_in_threadpool(semantic_search, q, top_k, source_file))["results"]
    results = []
    for model_id in model_list:
        try:
            report = await run_in_threadpool(
                generate_local_security_report_mode, q, evidence, model_id, "flow"
            )
            results.append(
                {
                    "model": model_id,
                    "report": report,
                    **{key: report.get(key) for key in ("risk_level", "summary", "inference_ms")},
                }
            )
        except Exception as exc:
            results.append({"model": model_id, "error": str(exc), "inference_ms": None})
    return {
        "query": q,
        "top_k": top_k,
        "source_file": source_file,
        "evidence": evidence,
        "results": results,
    }


@router.get("/history")
async def query_history(limit: int = Query(50, ge=1, le=200)):
    return {"history": await run_in_threadpool(get_query_history, limit)}


@router.get("/ips")
async def list_ips():
    return {"ips": await run_in_threadpool(list_all_ips)}


@router.get("/ips/{ip}")
async def ip_stats(ip: str):
    if len(ip) > 64:
        raise HTTPException(status_code=400, detail="Neispravna IP adresa.")
    return await run_in_threadpool(get_ip_stats, ip)


@router.get("/compare")
async def compare_search(
    q: str = Query(..., min_length=2, max_length=MAX_QUERY_LENGTH),
    top_k: int = Query(5, ge=1, le=MAX_TOP_K),
    source_file: str | None = Query(None, max_length=180),
):
    import time

    started = time.perf_counter()
    keyword = await run_in_threadpool(keyword_search, q, top_k, source_file)
    keyword_ms = round((time.perf_counter() - started) * 1000, 2)
    started = time.perf_counter()
    semantic = (await run_in_threadpool(semantic_search, q, top_k, source_file))["results"]
    semantic_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "query": q,
        "methodological_note": "Broj vraćenih rezultata nije mjera relevantnosti; rezultate treba ocijeniti na označenom benchmarku.",
        "keyword": {"results": keyword, "count": len(keyword), "time_ms": keyword_ms},
        "semantic": {"results": semantic, "count": len(semantic), "time_ms": semantic_ms},
    }


@router.get("/baseline/status")
async def baseline_status():
    return await run_in_threadpool(get_baseline_status)


@router.post("/baseline/train")
async def baseline_train(
    filename: str = Query(..., min_length=1, max_length=180),
    sample_size: int = Query(20000, ge=100, le=1_000_000),
):
    path = _resolve_upload(filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Datoteka nije pronađena.")
    return await run_in_threadpool(train_models, str(path), sample_size)


@router.get("/baseline/predict")
async def baseline_predict(
    filename: str = Query(..., min_length=1, max_length=180),
    row_index: int = Query(0, ge=0),
):
    dataframe = await run_in_threadpool(_load_csv, filename)
    dataframe = dataframe.rename(columns={str(c): str(c).strip() for c in dataframe.columns})
    if row_index >= len(dataframe):
        raise HTTPException(status_code=400, detail="Indeks retka je izvan raspona.")
    record = {str(key): value for key, value in dataframe.iloc[row_index].to_dict().items()}
    result = await run_in_threadpool(predict_record, record)
    result["actual_label"] = str(record.get("Label", "Unknown"))
    return result


@router.get("/baseline/evaluate")
async def baseline_evaluate(
    filename: str = Query(..., min_length=1, max_length=180),
    sample_size: int = Query(10000, ge=100, le=1_000_000),
):
    path = _resolve_upload(filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Datoteka nije pronađena.")
    return await run_in_threadpool(evaluate_on_file, str(path), sample_size)


@router.get("/classifier/llm/predict")
async def llm_classifier_predict(
    filename: str = Query(..., min_length=1, max_length=180),
    row_index: int = Query(0, ge=0),
    model: str = Query(..., min_length=1, max_length=100),
):
    """Classify one flow with an imported fine-tuned Ollama model."""
    dataframe = await run_in_threadpool(_load_csv, filename)
    dataframe = dataframe.rename(columns={str(c): str(c).strip() for c in dataframe.columns})
    if row_index >= len(dataframe):
        raise HTTPException(status_code=400, detail="Indeks retka je izvan raspona.")
    record = {str(key): value for key, value in dataframe.iloc[row_index].to_dict().items()}
    result = await run_in_threadpool(classify_flow, record, model)
    result["actual_label"] = str(record.get("Label", "Unknown"))
    result["source_file"] = filename
    result["source_row"] = row_index
    return result
