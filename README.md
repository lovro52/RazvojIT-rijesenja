# NetlogRAG — Analiza sigurnosnih prijetnji u mrežnim logovima pomoću RAG pristupa

> Projektni rad — Sveučilište Jurja Dobrile u Puli, Fakultet informatike  
> Diplomski studij informatike

---

## O projektu

NetlogRAG je AI sustav koji koristi **Retrieval-Augmented Generation (RAG)** pristup za analizu i interpretaciju mrežnih logova. Sustav omogućuje korisnicima postavljanje upita na prirodnom jeziku poput _"Postoje li sumnjive konekcije?"_ i dobivanje strukturiranih sigurnosnih izvještaja — bez potrebe za detaljnim tehničkim znanjem.

Projekt demonstrira primjenu RAG arhitekture u području **cybersecurity analitike** kombiniranjem semantičke pretrage s lokalnim jezičnim modelom.

---

## Arhitektura sustava

```
CSV logovi
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                     FastAPI Backend                      │
│                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │  Normalizacija│───▶│   ChromaDB   │    │  SQLite   │ │
│  │  CSV → JSON  │    │  (vektorska  │    │  (filter, │ │
│  └──────────────┘    │   baza)      │    │  povijest)│ │
│                      └──────┬───────┘    └───────────┘ │
│                             │ semantička pretraga        │
│                      ┌──────▼───────┐                   │
│                      │  Ollama LLM  │                   │
│                      │ llama3.1:8b  │                   │
│                      └──────┬───────┘                   │
│                             │ JSON izvještaj             │
└─────────────────────────────┼───────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   Vue.js Frontend   │
                    │  Upload / Filter /  │
                    │  Files / Query      │
                    └────────────────────┘
```

### Tehnologije

| Sloj | Tehnologija | Svrha |
|------|------------|-------|
| Backend | Python, FastAPI | REST API |
| Vektorska baza | ChromaDB | Pohrana i pretraga embeddings |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Semantička reprezentacija logova |
| LLM | Ollama (llama3.1:8b) | Generiranje sigurnosnih izvještaja |
| Relacijska baza | SQLite | Metapodaci, filtriranje, povijest |
| Frontend | Vue 3 + Vite | Korisničko sučelje |

---

## Struktura projekta

```
Diplomski/
├── main.py                        # FastAPI app, pokretanje servera
├── requirements.txt               # Python ovisnosti
├── .env.example                   # Primjer environment varijabli
├── sample_logs.csv                # Testni dataset
│
├── app/
│   ├── api/
│   │   └── logs.py                # Svi API endpointi
│   ├── core/
│   │   └── config.py              # Konfiguracija iz .env
│   └── services/
│       ├── normalize.py           # CSV → kanonički format
│       ├── vector_store.py        # ChromaDB + embeddings
│       ├── llm_local.py           # Ollama RAG generiranje
│       └── database.py            # SQLite operacije
│
├── data/                          # Generirano pri pokretanju (nije u gitu)
│   ├── uploads/                   # Uploadani CSV fajlovi
│   ├── chroma/                    # ChromaDB vektorska baza
│   └── logs.db                    # SQLite baza
│
└── frontend/                      # Vue.js aplikacija
    └── src/
        ├── App.vue                # Glavni layout i navigacija
        ├── main.js                # Router i inicijalizacija
        ├── style.css              # Globalni stilovi
        └── views/
            ├── UploadView.vue     # Upload i indeksiranje CSV-a
            ├── FilesView.vue      # Popis uploadanih fajlova
            ├── FilterView.vue     # Filtriranje po IP, vremenu, protokolu
            └── QueryView.vue      # RAG upit i prikaz izvještaja
```

---

## API endpointi

| Metoda | Endpoint | Opis |
|--------|----------|------|
| POST | `/logs/upload` | Upload CSV log fajla |
| POST | `/logs/index` | Normalizacija + embedding + pohrana u ChromaDB i SQLite |
| GET | `/logs/files` | Lista svih uploadanih fajlova |
| GET | `/logs/filter` | Filtriranje logova po IP, vremenu, protokolu, akciji |
| GET | `/logs/query/semantic` | Semantička pretraga po sličnosti |
| GET | `/logs/query/rag_local` | RAG upit — Ollama generira sigurnosni izvještaj |
| GET | `/health` | Provjera statusa servera |

---

## Postavljanje projekta

### Preduvjeti

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) s instaliranim modelom

### Backend

```bash
# 1. Klonirati repozitorij
git clone https://github.com/tvoje-ime/diplomski-rag.git
cd diplomski-rag

# 2. Kreirati i aktivirati virtualno okruženje
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# 3. Instalirati ovisnosti
pip install -r requirements.txt

# 4. Konfigurirati environment
cp .env.example .env

# 5. Pokrenuti Ollama model
ollama pull llama3.1:8b

# 6. Pokrenuti server
uvicorn main:app --reload
```

Backend je dostupan na **http://localhost:8000**  
Swagger dokumentacija: **http://localhost:8000/docs**

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend je dostupan na **http://localhost:5173**

---

## Korištenje

1. **Upload** — Uploadaj CSV fajl s mrežnim logovima
2. **Index** — Klikni "Index into Vector Store" da se logovi embedaju i pohrane
3. **Filter** — Filtriraj logove po izvornoj/odredišnoj IP adresi, vremenskom prozoru, protokolu ili akciji
4. **Query** — Postavi pitanje na prirodnom jeziku i dobij strukturirani sigurnosni izvještaj

### Format CSV fajla

Sustav prepoznaje sljedeće nazive stupaca:

| Polje | Prihvaćeni nazivi stupaca |
|-------|--------------------------|
| Timestamp | `timestamp`, `time`, `date`, `datetime` |
| Izvorišna IP | `src_ip`, `source_ip`, `src`, `ip_src` |
| Odredišna IP | `dst_ip`, `destination_ip`, `dst`, `ip_dst` |
| Protokol | `protocol`, `proto` |
| Akcija | `flag`, `action`, `event`, `label` |

---

## Sigurnosni izvještaj

Svaki RAG upit vraća strukturirani JSON izvještaj:

```json
{
  "risk_level": "HIGH | MEDIUM | LOW",
  "summary": "Kratko objašnjenje situacije",
  "key_indicators": ["Indikator 1", "Indikator 2"],
  "recommended_actions": ["Akcija 1", "Akcija 2"],
  "evidence_highlights": [
    {
      "id": "naziv_fajla.csv:3",
      "reason": "Zašto je ovaj log bitan"
    }
  ]
}
```

---

## Literatura

- Lewis, P. et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS.
- Canadian Institute for Cybersecurity. [CICIDS2017 Dataset](https://www.unb.ca/cic/datasets/ids-2017.html)
- ChromaDB Documentation. https://docs.trychroma.com
- LlamaIndex Documentation. https://docs.llamaindex.ai
- FastAPI Documentation. https://fastapi.tiangolo.com