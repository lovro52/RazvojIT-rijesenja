# Eksperimentalni protokol

Ovaj direktorij odvaja istraživačku evaluaciju od web aplikacije. Skripte ne upisuju velike skupove ili težine u Git.

## 1. Okruženje

Za QLoRA je potreban NVIDIA GPU. U Colabu odaberi GPU runtime i instaliraj:

```bash
pip install -r experiments/requirements-colab.txt
```

Pokreni svaki model u zasebnoj svježoj sesiji ako VRAM nije dovoljan za uzastopno učitavanje. Skripta u `training_report.json` automatski zapisuje GPU, verzije paketa, Git commit i seed.

## 2. Priprema podataka

```bash
python -m experiments.prepare_dataset \
  --input-dir /putanja/CICIDS2017 \
  --external-dir /putanja/CSE-CIC-IDS2018 \
  --output-dir data/experiments \
  --max-per-class 5000 \
  --seed 42
```

Izlaz:

- `train.jsonl`, `validation.jsonl`, `test.jsonl`: duplikatno grupirani, klasno stratificirani split 80/10/10;
- `external_test.jsonl`: odvojeni CSE-CIC-IDS2018 primjeri, ako je direktorij zadan;
- `dataset_report.json`: hash izvora, brojevi klasa, odbačene nepoznate oznake i konflikti.

Isti fingerprint značajki nikad ne smije biti u više splitova. Zapisi s istim značajkama, ali različitim oznakama odbacuju se i prijavljuju. Za završni rad dodatno provedi strožu podjelu po danu/datoteci prema `split_manifest.example.json`; taj rezultat treba prikazati odvojeno od glavnog duplikatno grupiranog splita.

## 3. QLoRA fine-tuning

Primjer za Qwen; promijeni ključ na `smollm3-3b` i `phi4-mini` za ostale modele:

```bash
python -m experiments.finetune \
  --model qwen3-1.7b \
  --data-dir data/experiments \
  --output-dir artifacts \
  --epochs 2 \
  --seed 42
```

Trening koristi 4-bit NF4 QLoRA, LoRA adapter na projekcijskim slojevima, determinističke seedove i validation loss za izbor najboljeg checkpointa. Ground-truth odgovor računa se iz oznake, a oznaka se ne nalazi u korisničkom promptu.

## 4. Base nasuprot fine-tuned modelu

```bash
python -m experiments.evaluate \
  --model qwen3-1.7b \
  --variant base \
  --dataset data/experiments/test.jsonl \
  --output reports/qwen3-base.json

python -m experiments.evaluate \
  --model qwen3-1.7b \
  --variant fine_tuned \
  --adapter artifacts/qwen3-1.7b/adapter \
  --dataset data/experiments/test.jsonl \
  --output reports/qwen3-finetuned.json
```

Ponovi na `external_test.jsonl`. Ne biraj hiperparametre prema testnom ili vanjskom testnom rezultatu. Za usporedbu koristi jednak broj primjera i jednak hardver.

## 5. Klasični baseline na istom splitu

Klasične modele evaluiraj na istim JSONL splitovima:

```bash
python -m experiments.evaluate_baselines \
  --train data/experiments/train.jsonl \
  --test data/experiments/test.jsonl \
  --model all \
  --output reports/baselines-test.json
```

Za vanjski test zamijeni samo `--test`; modeli se i dalje treniraju isključivo na internom `train.jsonl` skupu.

## 6. Spajanje i GGUF kvantizacija

Najprije kloniraj i izgradi službeni `llama.cpp`, zatim:

```bash
python -m experiments.export_quantize \
  --adapter artifacts/qwen3-1.7b/adapter \
  --merged-dir artifacts/qwen3-1.7b/merged \
  --llama-cpp-dir /putanja/llama.cpp \
  --output artifacts/qwen3-1.7b/netlog-qwen3-Q4_K_M.gguf \
  --quantization Q4_K_M \
  --ollama-tag netlog-qwen3:q4_k_m
```

Skripta sprema veličinu i SHA-256 GGUF datoteke. Ponovi i s nekvantiziranom ili višom preciznošću ako hardver dopušta kako bi se izmjerio gubitak kvalitete uzrokovan kvantizacijom.

## 7. Mjerenje stvarnog lokalnog inferencea

```bash
python -m experiments.evaluate_ollama \
  --model netlog-qwen3:q4_k_m \
  --dataset data/experiments/test.jsonl \
  --output reports/qwen3-q4_k_m-ollama.json \
  --warmup-runs 3
```

Prije mjerenja zatvori druge GPU procese. Navedi CPU, GPU, RAM/VRAM, OS, Ollama verziju, veličinu modela, context length, batch i broj warm-up prolaza. Medijan opisuje tipičan odziv, p95 rep distribucije, a `samples/s` propusnost serijskog prototipa.

## Minimalna tablica rezultata za rad

| Model | Varijanta | Interni macro-F1 | Vanjski macro-F1 | Invalid JSON | Median ms | p95 ms | samples/s | Veličina |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3 1.7B | base / QLoRA / Q4 |  |  |  |  |  |  |  |
| SmolLM3 3B | base / QLoRA / Q4 |  |  |  |  |  |  |  |
| Phi-4 mini | base / QLoRA / Q4 |  |  |  |  |  |  |  |
| Random Forest | baseline |  |  | n/a |  |  |  |  |
| XGBoost | baseline |  |  | n/a |  |  |  |  |

Glavni zaključak treba temeljiti na macro-F1, vanjskoj generalizaciji i računalnom trošku zajedno, a ne samo na accuracyju.
