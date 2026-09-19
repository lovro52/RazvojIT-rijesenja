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
    save_query,
    get_query_history,
    get_ip_stats,
    list_all_ips,
    keyword_search,
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
async def index_uploaded_csv(filename: str, auto_analyze: bool = True):
    df      = _load_csv(filename)
    records = normalize_dataframe(df)

    # Index into vector store
    count = index_records(records, source_filename=filename)

    # Save to SQLite
    save_log_records(records, source_file=filename)
    mark_file_indexed(filename)

    # Automatska analiza nakon indeksiranja
    auto_report = None
    if auto_analyze:
        try:
            query     = f"Analiziraj sigurnosne prijetnje u fajlu {filename}"
            retrieved = semantic_search(query=query, top_k=min(10, count))["results"]
            report    = generate_local_security_report(query=query, evidence=retrieved)
            save_query(
                query          = query,
                top_k          = min(10, count),
                report         = report,
                evidence_count = len(retrieved),
                queried_at     = datetime.utcnow().isoformat(),
            )
            auto_report = report
        except Exception:
            auto_report = None

    return {
        "message":         "indexed",
        "filename":        filename,
        "indexed_records": count,
        "auto_report":     auto_report,
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
    q:     str           = Query(...,          description="Security question to answer"),
    top_k: int           = Query(5,            description="Evidence records to retrieve"),
    model: Optional[str] = Query(None,         description="Ollama model ID to use"),
):
    retrieved = semantic_search(query=q, top_k=top_k)["results"]
    report    = generate_local_security_report(query=q, evidence=retrieved, model=model)

    save_query(
        query          = q,
        top_k          = top_k,
        report         = report,
        evidence_count = len(retrieved),
        queried_at     = datetime.utcnow().isoformat(),
    )

    return {
        "query":    q,
        "top_k":    top_k,
        "model":    report.get("model_used"),
        "report":   report,
        "evidence": retrieved,
    }


@router.get("/models", summary="List available Ollama models")
async def list_models():
    from app.core.config import AVAILABLE_MODELS
    return {"models": AVAILABLE_MODELS}


@router.get("/query/compare_models", summary="Run same query through multiple models and compare")
async def compare_models(
    q:      str = Query(..., description="Security question"),
    top_k:  int = Query(5,   description="Evidence records to retrieve"),
    models: str = Query("llama3.1:8b,llama3.2:1b", description="Comma-separated model IDs"),
):
    retrieved   = semantic_search(query=q, top_k=top_k)["results"]
    model_list  = [m.strip() for m in models.split(",") if m.strip()]
    results     = []

    for model_id in model_list:
        try:
            report = generate_local_security_report(
                query=q, evidence=retrieved, model=model_id
            )
            results.append({
                "model":        model_id,
                "risk_level":   report.get("risk_level"),
                "summary":      report.get("summary"),
                "inference_ms": report.get("inference_ms"),
                "report":       report,
            })
        except Exception as e:
            results.append({
                "model":  model_id,
                "error":  str(e),
                "inference_ms": None,
            })

    return {
        "query":    q,
        "top_k":    top_k,
        "evidence": retrieved,
        "results":  results,
    }

@router.get("/history", summary="Get query history")
async def query_history(limit: int = Query(50, description="Max number of results")):
    return {"history": get_query_history(limit=limit)}


@router.get("/ips", summary="List all unique source IP addresses")
async def list_ips():
    return {"ips": list_all_ips()}


@router.get("/ips/{ip}", summary="Detailed statistics for a specific IP address")
async def ip_stats(ip: str):
    return get_ip_stats(ip)


@router.get("/compare", summary="Compare keyword search vs semantic search")
async def compare_search(
    q:     str = Query(..., description="Search query"),
    top_k: int = Query(5,   description="Number of results"),
):
    import time

    # Keyword search
    t0      = time.perf_counter()
    keyword = keyword_search(query=q, limit=top_k)
    t_kw    = round((time.perf_counter() - t0) * 1000, 2)

    # Semantic search
    t0       = time.perf_counter()
    semantic = semantic_search(query=q, top_k=top_k)["results"]
    t_sem    = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "query": q,
        "keyword": {
            "results":     keyword,
            "count":       len(keyword),
            "time_ms":     t_kw,
        },
        "semantic": {
            "results":     semantic,
            "count":       len(semantic),
            "time_ms":     t_sem,
        },
    }


# ── Baseline ML endpoints ──────────────────────────────────────────────────
from app.services.baseline import train_models, predict_record, get_baseline_status

@router.get("/baseline/status", summary="Check if baseline models are trained")
async def baseline_status():
    return get_baseline_status()


@router.post("/baseline/train", summary="Train Random Forest + XGBoost on a CICIDS CSV")
async def baseline_train(
    filename:    str = Query(..., description="Uploaded CSV filename"),
    sample_size: int = Query(20000, description="Max rows to train on"),
):
    file_path = _upload_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found in uploads")

    result = train_models(csv_path=str(file_path), sample_size=sample_size)
    return result


@router.get("/baseline/predict", summary="Predict attack type for a log record")
async def baseline_predict(
    filename:    str = Query(..., description="Uploaded CSV filename"),
    row_index:   int = Query(0,   description="Row index to predict"),
):
    file_path = _upload_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found in uploads")

    import pandas as pd
    from typing import Any
    df  = pd.read_csv(file_path)
    df  = df.rename(columns={c: c.strip() for c in df.columns})

    if row_index >= len(df):
        raise HTTPException(status_code=400, detail="Row index out of range")

    record: dict[str, Any] = {str(k): v for k, v in df.iloc[row_index].to_dict().items()}
    result = predict_record(record)
    result["actual_label"] = str(record.get("Label", "Unknown"))
    return result


@router.get("/baseline/evaluate", summary="Evaluate trained models on an uploaded CSV")
async def baseline_evaluate(
    filename:    str = Query(..., description="Uploaded CSV filename"),
    sample_size: int = Query(10000, description="Max rows to evaluate on"),
):
    from app.services.baseline import evaluate_on_file
    file_path = _upload_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found in uploads")
    return evaluate_on_file(csv_path=str(file_path), sample_size=sample_size)


@router.get("/query/rag_local_mode", summary="RAG query with detection mode")
async def query_rag_local_mode(
    q:     str           = Query(...,  description="Security question"),
    top_k: int           = Query(5,    description="Evidence records to retrieve"),
    model: Optional[str] = Query(None, description="Ollama model ID"),
    mode:  str           = Query("auto", description="Detection mode: auto|text|flow"),
):
    from app.services.llm_local import generate_local_security_report_mode
    retrieved = semantic_search(query=q, top_k=top_k)["results"]
    report    = generate_local_security_report_mode(
        query=q, evidence=retrieved, model=model, mode=mode
    )

    save_query(
        query          = q,
        top_k          = top_k,
        report         = report,
        evidence_count = len(retrieved),
        queried_at     = datetime.utcnow().isoformat(),
    )

    return {
        "query":    q,
        "top_k":    top_k,
        "mode":     mode,
        "model":    report.get("model_used"),
        "report":   report,
        "evidence": retrieved,
    }


# ── Klasifikacija toka fine-tunanim modelom ────────────────────────────────
from app.services.llm_classifier import (
    ClassifierError, classify_batch, classify_flow,
)


def _instalirani_modeli() -> set[str]:
    """Nazivi modela registriranih u Ollami, bez oznake verzije.

    Oblik odgovora mijenjao se kroz verzije knjižnice `ollama`: starije vraćaju
    rječnik s ključem "models" i poljem "name", novije objekt s atributom
    `models` i poljem `model`. Podržavaju se oba oblika — inače se svi modeli
    prikažu kao neregistrirani, i onda kad jesu.
    """
    try:
        import ollama
        odgovor = ollama.list()
    except Exception:
        return set()

    stavke = getattr(odgovor, "models", None)
    if stavke is None and isinstance(odgovor, dict):
        stavke = odgovor.get("models", [])
    if not stavke:
        return set()

    nazivi: set[str] = set()
    for stavka in stavke:
        naziv = getattr(stavka, "model", None) or getattr(stavka, "name", None)
        if naziv is None and isinstance(stavka, dict):
            naziv = stavka.get("model") or stavka.get("name")
        if naziv:
            nazivi.add(str(naziv).split(":")[0])
    return nazivi


@router.get("/classifier/models", summary="Fine-tunani modeli za klasifikaciju toka")
async def classifier_models():
    from app.core.config import CLASSIFIER_MODEL, FINETUNED_MODELS
    from app.core.flow_schema import ATTACK_TYPES, SCHEMA_VERSION

    available = []
    installed = _instalirani_modeli()

    for m in FINETUNED_MODELS:
        available.append({**m, "installed": m["id"] in installed})

    return {
        "models":         available,
        "default":        CLASSIFIER_MODEL,
        "schema_version": SCHEMA_VERSION,
        "attack_types":   ATTACK_TYPES,
    }


@router.post("/classifier/classify", summary="Klasificiraj tokove iz uploadane datoteke")
async def classifier_classify(
    filename: str           = Query(..., description="Naziv uploadane CSV datoteke"),
    limit:    int           = Query(20,  description="Broj tokova (inferenca je spora)"),
    model:    Optional[str] = Query(None, description="ID fine-tunanog modela"),
):
    file_path = _upload_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Datoteka nije pronađena")

    import pandas as pd
    try:
        df = pd.read_csv(file_path, low_memory=False, encoding="latin-1")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV se ne može pročitati: {e}")

    records = normalize_dataframe(df, max_rows=max(limit * 5, 100))
    usable  = [r for r in records if r.get("flow_features")]

    if not usable:
        raise HTTPException(
            status_code=400,
            detail="Datoteka nema značajke toka potrebne za klasifikaciju "
                   "(očekuje se CICIDS2017 format).",
        )

    try:
        result = classify_batch(usable, model=model, limit=limit)
    except ClassifierError as e:
        raise HTTPException(status_code=503, detail=str(e))

    result["filename"] = filename
    return result


@router.post("/classifier/compare_rag", summary="Klasifikator vs RAG na istom toku")
async def classifier_compare_rag(
    filename:   str           = Query(..., description="Naziv uploadane CSV datoteke"),
    row_index:  int           = Query(0,   description="Indeks reda"),
    classifier: Optional[str] = Query(None, description="Fine-tunani model"),
    rag_model:  Optional[str] = Query(None, description="Opći model za RAG"),
):
    """
    Pokreće oba pristupa na istom toku.

    Klasifikator dobiva samo taj tok i prompt iz treninga; RAG sloj dobiva
    semantički dohvaćene dokaze i opći sustavski prompt. Usporedba pokazuje
    razliku u brzini i u tome što svaki pristup uopće može reći.
    """
    file_path = _upload_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Datoteka nije pronađena")

    import pandas as pd
    df      = pd.read_csv(file_path, low_memory=False, encoding="latin-1")
    records = normalize_dataframe(df, max_rows=max(row_index + 10, 100))

    if row_index >= len(records):
        raise HTTPException(status_code=400, detail="Indeks reda izvan raspona")

    rec = records[row_index]
    if not rec.get("flow_features"):
        raise HTTPException(status_code=400, detail="Red nema značajke toka")

    try:
        cls = classify_flow(rec["flow_features"], rec.get("protocol"), classifier)
    except ClassifierError as e:
        raise HTTPException(status_code=503, detail=str(e))

    retrieved = semantic_search(query=rec["message"], top_k=5)["results"]
    rag       = generate_local_security_report(
        query=rec["message"], evidence=retrieved, model=rag_model
    )

    return {
        "flow": {
            "message":      rec["message"],
            "src_ip":       rec.get("src_ip"),
            "dst_ip":       rec.get("dst_ip"),
            "dst_port":     rec.get("dst_port"),
            "ground_truth": rec.get("ground_truth"),
        },
        "classifier": {
            "attack_type":  cls["attack_type"],
            "risk_level":   cls["risk_level"],
            "summary":      cls["summary"],
            "inference_ms": cls["inference_ms"],
            "model":        cls["model_used"],
            "warnings":     cls["warnings"],
        },
        "rag": {
            "risk_level":   rag.get("risk_level"),
            "summary":      rag.get("summary"),
            "inference_ms": rag.get("inference_ms"),
            "model":        rag.get("model_used"),
            "evidence_count": len(retrieved),
        },
    }