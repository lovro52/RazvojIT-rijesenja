import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
CHROMA_DIR: str = os.getenv("CHROMA_DIR", "data/chroma")
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "data/uploads")
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
