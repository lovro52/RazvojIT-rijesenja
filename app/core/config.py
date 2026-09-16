import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
CHROMA_DIR:   str = os.getenv("CHROMA_DIR",   "data/chroma")
UPLOAD_DIR:   str = os.getenv("UPLOAD_DIR",   "data/uploads")
EMBED_MODEL:  str = os.getenv("EMBED_MODEL",  "sentence-transformers/all-MiniLM-L6-v2")

# Dostupni modeli za analizu
AVAILABLE_MODELS = [
    {
        "id":          "llama3.1:8b",
        "name":        "LLaMA 3.1 8B",
        "description": "Osnovni model — dobar balans brzine i kvalitete",
        "size":        "8B parametara",
        "provider":    "Meta",
        "type":        "baseline",
    },
    {
        "id":          "llama3.2:1b",
        "name":        "LLaMA 3.2 1B",
        "description": "Najbrži model — idealan za real-time detekciju",
        "size":        "1B parametara",
        "provider":    "Meta",
        "type":        "fast",
    },
    {
        "id":          "smollm2",
        "name":        "SmolLM2 1.7B",
        "description": "Kompaktan model optimiziran za fine-tuning",
        "size":        "1.7B parametara",
        "provider":    "HuggingFace",
        "type":        "compact",
    },
    {
        "id":          "phi3.5",
        "name":        "Phi-3.5 Mini",
        "description": "Microsoft model — odličan na dugačkim kontekstima",
        "size":        "3.8B parametara",
        "provider":    "Microsoft",
        "type":        "advanced",
    },
]

# Fine-tunani klasifikator toka (v3). Registrira se u Ollami iz GGUF fajla.
# Vidi docs/OLLAMA_SETUP.md za postupak.
CLASSIFIER_MODEL: str = os.getenv("CLASSIFIER_MODEL", "llama32-netlograg-v3")

# Fine-tunani modeli — klasifikacija pojedinog toka, NE RAG izvještaji.
FINETUNED_MODELS = [
    {
        "id":          "llama32-netlograg-v3",
        "name":        "LLaMA 3.2 1B (fine-tuned)",
        "base":        "meta-llama/Llama-3.2-1B-Instruct",
        "description": "Najbrži — 3.0 s po toku, 98.0 % točnosti",
        "size":        "1B parametara",
        "accuracy":    98.0,
        "latency_ms":  2998,
    },
    {
        "id":          "smollm2-netlograg-v3",
        "name":        "SmolLM2 1.7B (fine-tuned)",
        "base":        "HuggingFaceTB/SmolLM2-1.7B-Instruct",
        "description": "Najtočniji — 98.5 %, ali 10.5 s po toku",
        "size":        "1.7B parametara",
        "accuracy":    98.5,
        "latency_ms":  10486,
    },
    {
        "id":          "phi35-netlograg-v3",
        "name":        "Phi-3.5 Mini (fine-tuned)",
        "base":        "microsoft/Phi-3.5-mini-instruct",
        "description": "Najniži loss u treningu, najsporija inferenca",
        "size":        "3.8B parametara",
        "accuracy":    None,
        "latency_ms":  None,
    },
]