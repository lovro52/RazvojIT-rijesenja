# pyright: basic
from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from app.core.config import CHROMA_DIR, EMBED_MODEL, MIN_RETRIEVAL_SIMILARITY

COLLECTION_NAME = "network_incidents_v2"

_client = None
_collection = None
_embedder: SentenceTransformer | None = None


def get_client():
    global _client
    if _client is None:
        Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection():
    global _collection
    if _collection is None:
        _collection = get_client().get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine", "schema_version": "2"},
        )
    return _collection


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def _metadata(record: dict[str, Any], source_filename: str) -> dict[str, Any]:
    allowed = (
        "timestamp",
        "src_ip",
        "dst_ip",
        "src_port",
        "dst_port",
        "protocol",
        "action",
        "bytes",
        "record_type",
        "source_row_start",
        "source_row_end",
        "flow_count",
        "unique_destination_ips",
        "unique_destination_ports",
        "total_bytes",
        "total_forward_packets",
        "total_backward_packets",
        "total_syn_flags",
        "mean_bytes_per_second",
        "mean_packets_per_second",
    )
    metadata: dict[str, Any] = {"source": source_filename}
    for key in allowed:
        value = record.get(key)
        if value is not None:
            metadata[key] = value
    return metadata


def index_records(records: list[dict[str, Any]], source_filename: str) -> int:
    """Replace all vectors for one source file with the supplied records."""
    collection = get_collection()
    try:
        collection.delete(where={"source": source_filename})
    except Exception:
        # Chroma may raise when the source has never been indexed.
        pass

    if not records:
        return 0

    documents = [str(record["message"]) for record in records]
    embeddings = get_embedder().encode(documents, convert_to_numpy=True).tolist()
    ids = [
        f"{source_filename}:incident:{record.get('incident_index', index)}"
        for index, record in enumerate(records)
    ]
    metadatas = [_metadata(record, source_filename) for record in records]
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return len(records)


def delete_source(source_filename: str) -> None:
    """Remove every vector associated with one uploaded source file."""
    get_collection().delete(where={"source": source_filename})


def semantic_search(
    query: str,
    top_k: int = 5,
    source_file: str | None = None,
    min_similarity: float | None = MIN_RETRIEVAL_SIMILARITY,
) -> dict[str, Any]:
    """Search incident vectors, optionally scoped to exactly one source file.

    Similarity is a cosine-derived ranking score, not a calibrated probability.
    Results below ``min_similarity`` are excluded.
    """
    collection = get_collection()
    if collection.count() == 0:
        return {
            "query": query,
            "top_k": top_k,
            "source_file": source_file,
            "results": [],
        }

    query_embedding = get_embedder().encode([query], convert_to_numpy=True)[0].tolist()
    arguments: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if source_file:
        arguments["where"] = {"source": source_file}

    response: Any = collection.query(**arguments)
    ids = response.get("ids", [[]])[0]
    distances = response.get("distances", [[]])[0]
    documents = response.get("documents", [[]])[0]
    metadatas = response.get("metadatas", [[]])[0]

    results = []
    for record_id, distance, document, metadata in zip(
        ids, distances, documents, metadatas, strict=True
    ):
        similarity = max(0.0, min(1.0, 1.0 - float(distance)))
        if min_similarity is not None and similarity < min_similarity:
            continue
        results.append(
            {
                "id": record_id,
                "distance": round(float(distance), 6),
                "similarity": round(similarity, 6),
                "document": document,
                "metadata": metadata,
            }
        )

    return {
        "query": query,
        "top_k": top_k,
        "source_file": source_file,
        "results": results,
    }


def reset_state_for_tests() -> None:
    global _client, _collection, _embedder
    _client = None
    _collection = None
    _embedder = None
