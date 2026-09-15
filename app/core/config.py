from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Allows pure data utilities to run before dependencies are installed.

    def load_dotenv(*_args, **_kwargs) -> bool:
        return False


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def _path_setting(name: str, default: str) -> Path:
    value = Path(os.getenv(name, default)).expanduser()
    return value if value.is_absolute() else BASE_DIR / value


OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CHROMA_DIR = _path_setting("CHROMA_DIR", "data/chroma")
UPLOAD_DIR = _path_setting("UPLOAD_DIR", "data/uploads")
DB_PATH = _path_setting("DB_PATH", "data/logs.db")
MODEL_DIR = _path_setting("MODEL_DIR", "data/models")

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(250 * 1024 * 1024)))
MAX_NORMALIZED_ROWS = int(os.getenv("MAX_NORMALIZED_ROWS", "5000"))
MAX_QUERY_LENGTH = int(os.getenv("MAX_QUERY_LENGTH", "1000"))
MAX_TOP_K = int(os.getenv("MAX_TOP_K", "50"))
MAX_COMPARE_MODELS = int(os.getenv("MAX_COMPARE_MODELS", "3"))
MIN_RETRIEVAL_SIMILARITY = float(os.getenv("MIN_RETRIEVAL_SIMILARITY", "0.15"))


AVAILABLE_MODELS = [
    {
        "id": "llama3.1:8b",
        "name": "Llama 3.1 8B",
        "description": "General-purpose local model used as the RAG explainer.",
        "size": "8B parameters",
        "provider": "Meta",
        "type": "rag",
    },
    {
        "id": "qwen3:1.7b",
        "name": "Qwen3 1.7B",
        "description": "Compact base model for exploratory local RAG comparison.",
        "size": "1.7B parameters",
        "provider": "Qwen",
        "type": "rag",
    },
    {
        "id": "phi4-mini",
        "name": "Phi-4 Mini",
        "description": "Small base model for exploratory local RAG comparison.",
        "size": "3.8B parameters",
        "provider": "Microsoft",
        "type": "rag",
    },
]

FINE_TUNING_CANDIDATES = [
    {
        "hf_id": "Qwen/Qwen3-1.7B",
        "name": "Qwen3 1.7B",
        "license": "Apache-2.0",
        "planned_ollama_tag": "netlog-qwen3:latest",
    },
    {
        "hf_id": "HuggingFaceTB/SmolLM3-3B",
        "name": "SmolLM3 3B",
        "license": "Apache-2.0",
        "planned_ollama_tag": "netlog-smollm3:latest",
    },
    {
        "hf_id": "microsoft/Phi-4-mini-instruct",
        "name": "Phi-4 Mini Instruct",
        "license": "MIT",
        "planned_ollama_tag": "netlog-phi4-mini:latest",
    },
]
