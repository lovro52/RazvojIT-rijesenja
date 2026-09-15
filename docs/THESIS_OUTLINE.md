# Predložena struktura diplomskog rada

Naslov: **Analysis of Security Threats in Network Logs Using Large Language Models**

## Istraživački cilj

Ispitati koliko mali lokalni jezični modeli, prilagođeni QLoRA postupkom i kvantizirani za lokalno izvođenje, mogu klasificirati sigurnosne prijetnje u numeričkim zapisima mrežnih tokova te kako RAG može pomoći analitičaru u objašnjavanju agregiranih obrazaca.

## Istraživačka pitanja

- **RQ1:** Poboljšava li domenski QLoRA fine-tuning macro-F1 u odnosu na izvorni instruct model na istom testnom skupu?
- **RQ2:** Koliki je kompromis Q4_K_M kvantizacije između kvalitete, veličine modela, latencije i propusnosti?
- **RQ3:** Kako se tri lokalna LLM-a uspoređuju s Random Forestom i XGBoostom kada svi koriste istih 17 značajki i isti split?
- **RQ4:** Koliko se rezultati pogoršavaju na CSE-CIC-IDS2018 vanjskom testu i na podjeli po danu/datoteci?

Hipoteze treba zapisati prije završne evaluacije. Primjer provjerljive formulacije: “QLoRA povećava macro-F1 svakog modela na internom testu.” Nemoj formulirati hipotezu kao da je rezultat već poznat.

## Poglavlja

### 1. Uvod

- problem količine i složenosti mrežnih logova;
- motivacija za lokalne modele;
- cilj, istraživačka pitanja i doprinosi;
- opseg: flow značajke i pomoć analitičaru, ne potpuni produkcijski IDS.

### 2. Teorijska podloga i povezani radovi

- mrežni tokovi, IDS i obitelji napada;
- transformer i instruct LLM;
- LoRA, QLoRA i kvantizacija;
- RAG i ograničenja semantičkog dohvata numeričkih zapisa;
- klasični tablični modeli kao jaka referentna točka;
- pregled radova na CICIDS2017/2018 i rizik od curenja podataka.

### 3. Skupovi podataka i priprema

- porijeklo i licenca CICIDS2017 te CSE-CIC-IDS2018;
- 17 odabranih značajki i razlog odabira;
- mapiranje izvornih oznaka u devet obitelji;
- NaN/inf obrada, klasna raspodjela i uzorkovanje;
- fingerprint deduplikacija i konfliktne oznake;
- grouped 80/10/10 split i dodatni file/day split;
- hash datoteka i reproduktivnost.

### 4. Dizajn sustava

- Vue/FastAPI/Ollama/SQLite/ChromaDB arhitektura;
- normalizacija i agregiranje petominutnih incidenata;
- source-scoped retrieval;
- strukturirana JSON shema i validacija dokaza;
- audit podaci i sigurnost uploada;
- razdvajanje RAG izvještaja i klasifikacijskog endpointa.

### 5. Fine-tuning i kvantizacija

- opravdanje odabira Qwen3 1.7B, SmolLM3 3B i Phi-4 mini;
- zajednička prompt/completion shema;
- QLoRA NF4, LoRA ciljni linearni slojevi i hiperparametri;
- izbor checkpointa prema validation lossu;
- merge adaptera, GGUF i Q4_K_M;
- lokalni Ollama import.

### 6. Eksperimentalni protokol

- identičan test i značajke za sve modele;
- base, QLoRA i Q4 varijante;
- Random Forest i XGBoost baseline;
- determinističko dekodiranje i warm-up;
- primarna metrika macro-F1, 95% bootstrap interval;
- accuracy, per-class metrike, confusion matrix i invalid JSON;
- median/p95 latencija, samples/s, memorija, veličina i hardver;
- unaprijed definiran kriterij “real-time”.

### 7. Rezultati

- tablica kvalitete na internom testu;
- tablica vanjskog i file/day testa;
- tablica brzine, memorije i veličine;
- matrice zabune;
- analiza najčešćih pogrešaka i nevaljanih izlaza;
- odvojeni primjeri RAG izvještaja s provjerljivim dokazima.

### 8. Rasprava

- odgovori na RQ1–RQ4;
- kada je klasični ML bolji izbor;
- vrijednost i rizici LLM objašnjenja;
- privatnost i trošak lokalnog izvođenja bez apsolutnih GDPR tvrdnji;
- prijetnje unutarnjoj i vanjskoj valjanosti.

### 9. Zaključak i budući rad

- sažetak stvarno izmjerenih doprinosa;
- ograničenja prototipa;
- mogući payload dataset, streaming agregacija, kalibracija i ekspertna evaluacija izvještaja.

## Obvezne tablice i slike

- arhitektura sustava i odvojeni RAG/klasifikacijski tok;
- raspodjela klasa prije i poslije uzorkovanja;
- mapa izvornih u objedinjene oznake;
- hiperparametri i hardver po modelu;
- kvaliteta base/QLoRA/Q4 + baseline;
- interni nasuprot vanjskom/file-day testu;
- latencija, propusnost, VRAM i veličina;
- najmanje jedna matrica zabune po važnoj varijanti;
- kvalitativni primjeri RAG odgovora s ID-evima dokaza i ljudskom kritikom.
