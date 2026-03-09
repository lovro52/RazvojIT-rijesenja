# pyright: basic
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from app.core.config import CHROMA_DIR, EMBED_MODEL

COLLECTION_NAME = "network_logs"

_client = None
_collection = None
_embedder: Optional[SentenceTransformer] = None


def get_client():
    global _client
    if _client is None:
        Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(  # type: ignore[call-arg]
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection():
    global _collection
    if _collection is None:
        _collection = get_client().get_or_create_collection(name=COLLECTION_NAME)
    return _collection


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def index_records(records: List[Dict[str, Any]], source_filename: str) -> int:
    col      = get_collection()
    embedder = get_embedder()

    docs = [r["message"] for r in records]
    embs = embedder.encode(docs, convert_to_numpy=True).tolist()  # type: ignore[union-attr]
    ids  = [f"{source_filename}:{i}" for i in range(len(records))]

    metas = [
        {
            "timestamp": r.get("timestamp"),
            "src_ip":    r.get("src_ip"),
            "dst_ip":    r.get("dst_ip"),
            "src_port":  r.get("src_port"),
            "dst_port":  r.get("dst_port"),
            "protocol":  r.get("protocol"),
            "action":    r.get("action"),
            "bytes":     r.get("bytes"),
            "source":    source_filename,
        }
        for r in records
    ]

    try:
        col.delete(ids=ids)
    except Exception:
        pass

    col.add(ids=ids, documents=docs, embeddings=embs, metadatas=metas)  # type: ignore[arg-type]
    return len(records)


def semantic_search(query: str, top_k: int = 5) -> Dict[str, Any]:
    col      = get_collection()
    embedder = get_embedder()

    q_emb = embedder.encode([query], convert_to_numpy=True)[0].tolist()  # type: ignore[union-attr]
    res: Any = col.query(  # type: ignore[arg-type]
        query_embeddings=[q_emb],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]  # type: ignore[arg-type],
    )

    return {
        "query":   query,
        "top_k":   top_k,
        "results": [
            {
                "id":       res["ids"][0][i],
                "distance": res["distances"][0][i],
                "document": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
            }
            for i in range(len(res["ids"][0]))
        ],
    }