# NetlogRAG — Analiza sigurnosnih prijetnji u mrežnim zapisima primjenom velikih jezičnih modela

> **Diplomski rad**
>
> | | |
> |---|---|
> | Autor | Lovro Luka Matan (JMBAG: 0114035988, redoviti student) |
> | Naslov rada | Analiza sigurnosnih prijetnji u mrežnim zapisima primjenom velikih jezičnih modela |
> | Vrsta rada | Diplomski rad |
> | Ustanova | Sveučilište Jurja Dobrile u Puli, Fakultet informatike u Puli |
> | Studijski smjer | Informatika |
> | Kolegij | Razvoj IT rješenja |
> | Znanstveno područje | Društvene znanosti |
> | Znanstveno polje | Informacijske znanosti |
> | Znanstvena grana | Informacijski sustavi i informatologija |
> | Mentor | izv. prof. dr. sc. Nikola Tanković |
> | Mjesto i datum | Pula, rujan 2026. |

---

## O projektu

NetlogRAG je sustav za analizu mrežnih sigurnosnih zapisa koji se u cijelosti izvodi na lokalnom računalu, bez slanja podataka vanjskim uslugama. Sastoji se od dva odvojena sloja:

- **klasifikacijski sloj** — prilagođeni jezični model (LLaMA 3.2 1B, prilagođen postupkom QLoRA i kvantiziran u format GGUF) određuje tip napada i razinu rizika pojedinog mrežnog toka;
- **sloj dohvata i generiranja (RAG)** — semantičkom pretragom nad vektorskom bazom dohvaća zapise slične korisničkom pitanju, a opći model (llama3.1:8b) na temelju njih piše sigurnosni izvještaj s dokazima.

Uz jezične modele sustav sadrži i dva klasična modela strojnog učenja (Random Forest i XGBoost) kao referentnu točku za usporedbu. Modeli su trenirani i vrednovani na skupu podataka CICIDS2017 svedenom na sedam klasa.

---

## Arhitektura sustava

```
CSV zapisi
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI poslužitelj                        │
│                                                              │
│  Normalizacija ──► ChromaDB (ugrađivanja)    SQLite          │
│        │                 │ semantička pretraga (povijest,   │
│        │                 ▼                    filtriranje)   │
│        │         Ollama: llama3.1:8b ──► sigurnosni izvještaj│
│        │                                                     │
│        └──────► Ollama: llama32-netlograg-v3 ──► tip napada  │
│                 (prilagođeni klasifikator)       i rizik     │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
                     Vue 3 sučelje (12 pogleda)
```

### Tehnologije

| Sloj | Tehnologija | Svrha |
|------|------------|-------|
| Poslužitelj | Python, FastAPI | sučelje za programiranje aplikacija |
| Vektorska baza | ChromaDB | pohrana ugrađivanja i pretraga po sličnosti |
| Ugrađivanja | sentence-transformers (all-MiniLM-L6-v2) | pretvorba zapisa u vektore |
| Jezični modeli | Ollama (llama3.1:8b, llama32-netlograg-v3) | izvještaji i klasifikacija toka |
| Usporedni modeli | scikit-learn (Random Forest), XGBoost | referentna točka |
| Relacijska baza | SQLite | zapisi, povijest upita |
| Sučelje | Vue 3 + Vite | korisničko sučelje |

---

## Struktura repozitorija

```
RazvojIT-rijesenja/
├── main.py                         # FastAPI aplikacija
├── requirements.txt                # Python ovisnosti
├── env.example                     # primjer postavki (.env)
├── app/
│   ├── api/logs.py                 # sve rute sučelja
│   ├── core/config.py              # postavke i popis modela
│   ├── core/flow_schema.py         # zajednička shema treniranja i aplikacije
│   └── services/
│       ├── normalize.py            # CSV → zajednički oblik zapisa
│       ├── vector_store.py         # ChromaDB i ugrađivanja
│       ├── llm_local.py            # izvještaji (dohvat i generiranje)
│       ├── llm_classifier.py       # klasifikacija toka prilagođenim modelom
│       ├── baseline.py             # Random Forest i XGBoost
│       └── database.py             # SQLite
├── scripts/
│   ├── evaluiraj_gguf.py           # vrednovanje kvantiziranih modela (poglavlje 8)
│   ├── baseline_usporedba.py       # usporedba s klasičnim modelima (odjeljak 8.10)
│   ├── ponovno_mjerenje.ps1        # ponavljanje svih mjerenja
│   ├── test_klasifikator.py        # brza provjera klasifikatora
│   └── uat_netlograg.py            # test korisničkog prihvaćanja (odjeljak 8.11)
├── notebooks/                      # bilježnice za prilagodbu i izvoz modela (Google Colab)
├── rezultati/                      # izmjereni rezultati u obliku JSON
├── docs/OLLAMA_SETUP.md            # registracija GGUF modela u Ollami
└── frontend/                       # Vue 3 sučelje
```

Mapa `data/` (učitane datoteke, vektorska baza, SQLite) nastaje pri pokretanju i nije u repozitoriju, kao ni GGUF datoteke modela i datoteke skupa CICIDS2017.

---

## Postavljanje

### Preduvjeti

- Python 3.11+
- Node.js 20+
- [Ollama](https://ollama.com) s modelom `llama3.1:8b` i registriranim prilagođenim modelom (vidi `docs/OLLAMA_SETUP.md`)

### Poslužitelj

```bash
git clone https://github.com/lovro52/RazvojIT-rijesenja.git
cd RazvojIT-rijesenja

python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
copy env.example .env           # Windows  (cp env.example .env na macOS / Linuxu)

ollama pull llama3.1:8b
uvicorn main:app --reload
```

Poslužitelj je dostupan na **http://localhost:8000**, a dokumentacija sučelja na **http://localhost:8000/docs**.

### Sučelje

```bash
cd frontend
npm install
npm run dev
```

Sučelje je dostupno na **http://localhost:5173**.

---

## Glavne rute sučelja

| Metoda | Ruta | Opis |
|--------|------|------|
| POST | `/logs/upload` | učitavanje CSV datoteke |
| POST | `/logs/normalize` | normalizacija učitane datoteke |
| POST | `/logs/index` | normalizacija, ugrađivanje i pohrana (najviše 5000 nasumično odabranih zapisa) |
| GET | `/logs/files` | popis učitanih datoteka |
| GET | `/logs/filter` | filtriranje po adresi, vremenu, protokolu, radnji |
| GET | `/logs/query/semantic` | semantička pretraga |
| GET | `/logs/compare` | usporedba pretrage po ključnim riječima i semantičke pretrage |
| GET | `/logs/query/rag_local_mode` | pitanje — izvještaj s dokazima |
| GET | `/logs/query/compare_models` | isto pitanje za više modela |
| GET | `/logs/history` | povijest pitanja |
| GET | `/logs/classifier/models` | dostupni prilagođeni modeli |
| POST | `/logs/classifier/classify` | klasifikacija tokova prilagođenim modelom |
| POST | `/logs/classifier/compare_rag` | klasifikator i dohvat na istom toku |
| GET/POST | `/logs/baseline/...` | Random Forest i XGBoost |
| GET | `/health` | provjera rada poslužitelja |

### Format CSV datoteke

Sustav prepoznaje datoteke skupa CICIDS2017 (MachineLearningCSV) i jednostavne zapise sa sljedećim stupcima:

| Polje | Prihvaćeni nazivi stupaca |
|-------|--------------------------|
| Vremenska oznaka | `timestamp`, `time`, `date`, `datetime` |
| Izvorišna adresa | `src_ip`, `source_ip`, `src`, `ip_src` |
| Odredišna adresa | `dst_ip`, `destination_ip`, `dst`, `ip_dst` |
| Protokol | `protocol`, `proto` (broj ili naziv) |
| Radnja | `flag`, `action`, `event` |

Stupac `Label`, kad postoji, čuva se odvojeno kao istinita oznaka i ne ulazi u tekst koji se indeksira niti u upit modelu.

---

## Ponavljanje mjerenja

Rezultati iz poglavlja 8 rada nalaze se u mapi `rezultati/`. Mjerenja se ponavljaju skriptama:

```bash
python scripts/evaluiraj_gguf.py --model llama32-netlograg-v3 --limit 600 --csv <datoteke CICIDS2017> ...
python scripts/baseline_usporedba.py --csv <datoteke CICIDS2017> ...
```

ili cijelim nizom preko `scripts/ponovno_mjerenje.ps1`. Prilagodba i izvoz modela u GGUF provode se u bilježnicama u mapi `notebooks/` (Google Colab, grafička kartica Tesla T4).

## Test korisničkog prihvaćanja

```bash
python scripts/uat_netlograg.py --tester "T1 (autor)"
```

Skripta pokreće zasebnu instancu poslužitelja u izdvojenom ispitnom okruženju, izvodi scenarije po funkcionalnim cjelinama i rezultate zapisuje u `rezultati/uat_rezultati.json` i `rezultati/uat_rezultati.md`.

---

## Literatura

Potpun popis literature nalazi se u radu. Najvažniji izvori:

- P. Lewis i dr., „Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks", NeurIPS 2020.
- T. Dettmers i dr., „QLoRA: Efficient Finetuning of Quantized LLMs", NeurIPS 2023.
- I. Sharafaldin, A. H. Lashkari i A. A. Ghorbani, „Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization", ICISSP 2018. [CICIDS2017](https://www.unb.ca/cic/datasets/ids-2017.html)
- Chroma, dokumentacija: https://docs.trychroma.com