# Izvještaj o reviziji projekta

Projekt: **Analysis of Security Threats in Network Logs Using Large Language Models**  
Radna grana: `codex/thesis-revision`  
Status: tehnička i metodološka revizija prototipa; rezultati GPU eksperimenata još nisu izvedeni.

## Sažeta objektivna ocjena

Izvorni projekt imao je dobru demonstracijsku širinu: funkcionalan Vue/FastAPI tok, lokalni Ollama, ChromaDB, SQLite i klasične baseline modele. Najveći problem nije bio izgled aplikacije nego valjanost istraživačkih tvrdnji. Izolirani mrežni tok nije dovoljan dokaz za DDoS, port scan ili brute-force; slučajni row split može dati optimističan rezultat zbog duplikata; a fine-tuning klasifikatora nije isto što i RAG generiranje izvještaja.

Revizija ta tri problema razdvaja u provjerljive cjeline. Projekt je sada znatno bliže kvaliteti diplomskog rada, ali nije dovršen dok se ne izvrše sva tri modela, vanjski test i mjerenja kvantiziranog lokalnog inferencea.

## Nalazi i status

| Prioritet | Izvorni nalaz | Revizija | Status |
|---|---|---|---|
| Kritično | Oznaka ili semantika oznake mogla je utjecati na prikaz/dohvat | `ground_truth` je odvojen od poruke, embeddinga i inference prompta | riješeno u kodu |
| Kritično | RAG je zaključivao iz pojedinačnih tokova | tokovi se grupiraju po izvoru i petominutnom prozoru | riješeno u kodu |
| Kritično | Fine-tuning i aplikacija nisu imali ugovorenu istu shemu | zajednički `netlog-flow-classification-v1` i API za kvantizirani klasifikator | riješeno u kodu |
| Visoko | Random row split mogao je propustiti duplikate u test | fingerprint grupe ostaju u jednom splitu, konflikti se odbacuju | riješeno u kodu |
| Visoko | Auto-analiza nije bila ograničena na upravo indeksiranu datoteku | source-scoped retrieval i UI odabir izvora | riješeno u kodu |
| Visoko | Baseline inference nije jamčio isti redoslijed značajki | redoslijed se sprema u metadata i strogo primjenjuje | riješeno u kodu |
| Visoko | Upload je dopuštao rizične putanje i nije imao veličinski limit | siguran naziv, provjera putanje, streaming limit, privremena datoteka | riješeno u kodu |
| Srednje | Slobodni LLM tekst mogao je izgledati valjano | Pydantic JSON shema, `UNKNOWN` fallback i provjera ID-eva dokaza | riješeno u kodu |
| Srednje | UI je heuristike prikazivao kao detekciju | neutralni nazivi signala i jasna ograničenja | riješeno u kodu |
| Srednje | “Lokalno znači GDPR/real-time/superiorno” | tvrdnje su ublažene i vezane uz mjerenje i organizacijske kontrole | riješeno u dokumentaciji/UI-ju |
| Srednje | Nedostajali su testovi i CI | unit testovi, Ruff, frontend lint/build i GitHub Actions | riješeno u kodu; CI treba potvrditi |

## Što još mora biti napravljeno prije predaje

1. Izvršiti QLoRA trening za Qwen3 1.7B, SmolLM3 3B i Phi-4 mini na zaključanim splitovima.
2. Za sva tri modela prijaviti base, fine-tuned i Q4_K_M rezultate, bez biranja najboljeg checkpointa prema testu.
3. Izvršiti isti interni test za Random Forest i XGBoost na 17 zajedničkih značajki.
4. Nabaviti i dokumentirati CSE-CIC-IDS2018 ili obrazložiti zašto vanjski test nije izvediv. Mapiranje oznaka mora ostati zabilježeno.
5. Dodati stroži eksperiment podjele po danu/datoteci. Ako rezultat padne u odnosu na grouped random split, to je važan nalaz, ne greška koju treba sakriti.
6. Unaprijed definirati što “real-time” znači za scenarij rada: interaktivni RAG odziv ili broj klasificiranih tokova u sekundi. Zatim usporediti p95/propusnost s tim pragom.
7. U tablice uključiti hardver, VRAM, verzije paketa, seed, broj primjera, trajanje treninga, veličinu adaptera/GGUF-a i stopu nevaljanog JSON izlaza.
8. Dodati licencu vlastitog koda i provjeriti dopuštenja za distribuciju skupova i izvedenih modela.
9. U pisanom radu odvojiti rezultate RAG potpore analitičaru od rezultata klasifikacije pojedinog toka.

## Predloženi kriterij završne kvalitete

Rad je spreman za obranu kada se svaka glavna tvrdnja može povezati s: verzijom koda, hashom podataka, točno navedenim modelom, konfiguracijom, metrikom i ograničenjem. Vizualno dobro sučelje je plus, ali neće nadomjestiti curenje podataka, neusporediv eksperimentalni protokol ili nedokumentiran hardver.
