# RAG Security Log Analyzer

A FastAPI application that ingests network log CSVs, indexes them with semantic embeddings (ChromaDB + sentence-transformers), and answers security questions using a local Ollama LLM.

---

## Project structure

```
rag_security/
├── main.py                    # FastAPI app entry point
├── requirements.txt
├── .env.example               # Copy to .env and edit
├── sample_logs.csv
└── app/
    ├── __init__.py
    ├── api/
    │   ├── __init__.py
    │   └── logs.py            # All /logs routes
    ├── core/
    │   ├── __init__.py
    │   └── config.py          # Reads .env variables
    └── services/
        ├── __init__.py
        ├── normalize.py       # CSV → canonical records
        ├── vector_store.py    # ChromaDB + embeddings
        └── llm_local.py       # Ollama RAG report generation
```

---

## Setup

### 1. Clone / open the folder in VS Code

```bash
cd rag_security
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env if you want a different Ollama model
```

### 5. Make sure Ollama is running with your model

```bash
ollama pull llama3.1:8b
ollama serve
```

### 6. Run the server

```bash
uvicorn main:app --reload
```

Open **http://localhost:8000/docs** for the interactive Swagger UI.

---

## API workflow

| Step | Method | Endpoint | Description |
|------|--------|----------|-------------|
| 1 | POST | `/logs/upload` | Upload a `.csv` log file |
| 2 | POST | `/logs/index` | Embed and store logs in ChromaDB |
| 3 | GET  | `/logs/query/semantic` | Semantic similarity search |
| 4 | GET  | `/logs/query/rag_local` | Full RAG answer from Ollama |

### Quick test with the sample CSV

```bash
# 1. Upload
curl -X POST http://localhost:8000/logs/upload \
  -F "file=@sample_logs.csv"

# 2. Index (use the filename returned above)
curl -X POST "http://localhost:8000/logs/index?filename=<returned_filename>"

# 3. Ask a question
curl "http://localhost:8000/logs/query/rag_local?q=Are+there+any+suspicious+connections"
```

---

## VS Code tips

- Select your `.venv` as the Python interpreter: `Ctrl+Shift+P` → *Python: Select Interpreter* → choose `.venv`
- Install the **Python** and **Pylance** extensions for proper import resolution
- The project root (`rag_security/`) must be your workspace root so that `app.*` imports resolve correctly
