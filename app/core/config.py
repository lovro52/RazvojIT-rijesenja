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