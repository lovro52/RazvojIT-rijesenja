# Registracija fine-tunanih modela u Ollami

GGUF datoteke nastaju u Colabu (`NetlogRAG_Evaluacija_v3.ipynb`, ćelija 11)
i spremaju se na Google Drive. Ovdje je postupak da ih aplikacija može koristiti.

## 1. Pripremi direktorij

```
C:\Projects\Diplomski\models\
├── llama32-1b-netlograg-v3-Q4_K_M.gguf
├── smollm2-1.7b-netlograg-v3-Q4_K_M.gguf
└── phi35-mini-netlograg-v3-Q4_K_M.gguf
```

## 2. Modelfile

Za svaki model napravi zasebnu datoteku bez ekstenzije.

**Bitno je da `TEMPLATE` odgovara formatu iz treninga.** Modeli su trenirani
na blokovima `### Instruction / ### Input / ### Response`. Ako se ubace s
podrazumijevanim LLaMA ili Phi predloškom, dobiju prompt kakav nikad nisu
vidjeli i fine-tuning se gubi.

`Modelfile.llama`:

```
FROM ./llama32-1b-netlograg-v3-Q4_K_M.gguf

TEMPLATE """### Instruction:
{{ .Prompt }}

### Response:
"""

PARAMETER temperature 0.1
PARAMETER num_predict 220
PARAMETER stop "### Instruction:"
PARAMETER stop "### Input:"
PARAMETER stop "### Response:"
```

Isto za `Modelfile.smollm2` i `Modelfile.phi`, samo zamijeni `FROM` liniju.

> Aplikacija šalje cijeli prompt kroz `ollama.generate()`, uključujući
> `### Instruction:` i `### Input:` blokove. `TEMPLATE` zato ostaje minimalan —
> vidi `app/core/flow_schema.py`.

## 3. Registracija

```bash
cd C:\Projects\Diplomski\models

ollama create llama32-netlograg-v3  -f Modelfile.llama
ollama create smollm2-netlograg-v3  -f Modelfile.smollm2
ollama create phi35-netlograg-v3    -f Modelfile.phi

ollama list
```

## 4. Provjera

```bash
ollama run llama32-netlograg-v3 "### Input:
TCP tok. FlowDuration=1200.0, FwdPkts=8.0, BwdPkts=6.0, FlowBytes/s=2353.3, SYNFlagCount=1.0"
```

Očekivani izlaz je JSON s poljima `attack_type` i `risk_level`. Ako model
vrati slobodan tekst ili nastavi generirati nove `### Input:` blokove,
`TEMPLATE` ili `stop` parametri nisu ispravno postavljeni.

## 5. Konfiguracija aplikacije

U `.env`:

```
# Opći model — RAG izvještaji iz više dohvaćenih dokaza
OLLAMA_MODEL=llama3.1:8b

# Fine-tunani model — klasifikacija pojedinačnog toka
CLASSIFIER_MODEL=llama32-netlograg-v3
```

Dvije odvojene postavke jer su to dva različita zadatka. Fine-tunani model
nije treniran na RAG promptu i na njemu bi radio lošije od općeg modela.

## 6. Endpointi

| Metoda | Endpoint | Opis |
|---|---|---|
| GET | `/logs/classifier/models` | Popis modela i je li koji instaliran |
| POST | `/logs/classifier/classify` | Klasifikacija tokova iz datoteke |
| POST | `/logs/classifier/compare_rag` | Klasifikator vs RAG na istom toku |

Klasifikacija je spora — sekunde po toku — pa `limit` prema zadanome
obrađuje 20 tokova.