#!/usr/bin/env python3
"""
Evaluacija kvantiziranog (GGUF) modela na istom testnom skupu kao u Colabu.

Zašto postoji
─────────────
U Colabu je model evaluiran kao bitsandbytes NF4 model sa živim LoRA adapterom,
na GPU-u i s greedy dekodiranjem (`do_sample=False`), i dao je 98.0 % točnosti.
Lokalno se izvršava kao Q4_K_M GGUF spojenog modela, na CPU-u, kroz Ollamu.
Razlika između tog dvoga je mjerljiva veličina — u radu se zove *quantization
degradation* i profesor ju je izrijekom tražio.

Da razlika ne bi bila pripisana kvantizaciji kad zapravo dolazi od dekodiranja,
prekidač `--greedy` postavlja Ollamu na isto dekodiranje koje je koristio Colab.
Bez njega Ollama uzorkuje (top_k 40, top_p 0.9), što je drukčiji postupak.

Ova skripta rekonstruira **točno isti** testni skup koji je notebook koristio
(ista logika uzorkovanja, isti seed 42, isti split po klasi) i propušta ga kroz
lokalnu Ollamu. Rezultat je izravno usporediv s `rezultati/report_*.json`.

Provjera ispravnosti rekonstrukcije
───────────────────────────────────
Ako se lokalni split makar malo razlikuje od Colabovog, dio testnih primjera
zapravo je bio u treningu i točnost bi bila lažno visoka. Zato skripta ne
vjeruje sama sebi: uspoređuje raspodjelu klasa u prvih 200 testnih primjera s
onom zapisanom u `report_*.json`. Ako se ne poklapa, odbija nastaviti.

Pokretanje
──────────
    python scripts/evaluiraj_gguf.py --csv-dir "C:\\Projects\\Diplomski\\CIC-IDS-2017"
    python scripts/evaluiraj_gguf.py --csv-dir ... --model smollm2-netlograg-v3
    python scripts/evaluiraj_gguf.py --csv-dir ... --limit 50        # brza proba
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import numpy as np
    import pandas as pd
except ImportError:
    sys.exit("Nedostaju paketi. Instaliraj: pip install pandas numpy")

try:
    import ollama
except ImportError:
    sys.exit("Nedostaje paket 'ollama'. Instaliraj: pip install ollama")

from app.services.llm_classifier import _extract_json

# ═══════════════════════════════════════════════════════════════════════
# Doslovna kopija logike iz NetlogRAG_FineTuning_v2.ipynb, ćelija 12 i 14.
# Ne smije se "poboljšavati" — svaka izmjena mijenja testni skup i rezultat
# prestaje biti usporediv s Colabom.
# ═══════════════════════════════════════════════════════════════════════

SAMPLE_PER_CLASS = 1200
SEED = 42

FLOW_FEATURES = [
    "Flow Duration",
    "Total Fwd Packets", "Total Backward Packets",
    "Total Length of Fwd Packets", "Total Length of Bwd Packets",
    "Fwd Packet Length Mean", "Bwd Packet Length Mean",
    "Flow Bytes/s", "Flow Packets/s",
    "Flow IAT Mean", "Flow IAT Std",
    "SYN Flag Count", "PSH Flag Count", "ACK Flag Count",
    "Down/Up Ratio", "Average Packet Size",
]

_BASE_MAP = {
    "BENIGN":           ("BENIGN",       "LOW"),
    "FTP-Patator":      ("FTP-Patator",  "HIGH"),
    "SSH-Patator":      ("SSH-Patator",  "HIGH"),
    "DoS Hulk":         ("DoS",          "HIGH"),
    "DoS GoldenEye":    ("DoS",          "HIGH"),
    "DoS slowloris":    ("DoS",          "HIGH"),
    "DoS Slowhttptest": ("DoS",          "HIGH"),
    "Heartbleed":       ("DoS",          "HIGH"),
    "DDoS":             ("DDoS",         "HIGH"),
    "PortScan":         ("PortScan",     "MEDIUM"),
    "Bot":              ("Botnet",       "HIGH"),
    "Infiltration":     ("Infiltration", "HIGH"),
}


def map_label(label: str) -> tuple[str, str]:
    """
    Labela → (tip napada, razina rizika).

    Web napadi se ne mapiraju preko rječnika nego preko ključnih riječi, jer
    CICIDS2017 razdjelnik u "Web Attack – Brute Force" isporučuje ovisno o
    kodiranju kao en-dash, obični minus, `?` ili `\ufffd`. Rječnik bi te
    retke tiho preskočio i klasa WebAttack bi nestala iz dataseta.
    """
    raw = str(label).strip()
    if raw in _BASE_MAP:
        return _BASE_MAP[raw]

    low = raw.lower()
    if "web attack" in low:
        return ("WebAttack", "HIGH")
    return ("Unknown", "MEDIUM")


def _safe_float(value) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if np.isnan(v) or np.isinf(v):
        return None
    return v


def build_input_text(row) -> str:
    """Identično `build_instruction` iz notebooka, samo bez izlaznog JSON-a."""
    parts = []
    for feat in FLOW_FEATURES:
        v = _safe_float(row.get(feat))
        if v is None:
            continue
        short = (feat.replace("Total ", "").replace("Length of ", "Len")
                     .replace("Packet", "Pkt").replace("Backward", "Bwd")
                     .replace("Forward", "Fwd").replace(" ", ""))
        parts.append(f"{short}={v:.1f}")

    pv = _safe_float(row.get("Protocol"))
    proto = {"6": "TCP", "17": "UDP", "1": "ICMP"}.get(
        str(int(pv)) if pv is not None else "", "TCP")

    return f"{proto} tok. " + ", ".join(parts)


PROMPT_TEMPLATE = (
    "### Instruction:\nAnaliziraj karakteristike ovog mrežnog toka, "
    "odredi tip napada i procijeni razinu rizika. Vrati ISKLJUČIVO JSON.\n\n"
    "### Input:\n{inp}\n\n"
    "### Response:\n"
)

# Raspodjela klasa u prvih 200 testnih primjera, prepisana iz
# rezultati/report_llama32-1b-netlograg-v3.json. Služi kao kontrolni zbroj:
# ako se lokalna rekonstrukcija poklapa s ovim, split je identičan Colabovom.
FINGERPRINT_V3 = {
    "FTP-Patator": 33, "PortScan": 32, "DoS": 31, "SSH-Patator": 30,
    "DDoS": 30, "WebAttack": 23, "BENIGN": 21,
}


def ucitaj_csvove(putanje: list[Path]) -> pd.DataFrame:
    dfs = []
    for p in putanje:
        df = pd.read_csv(p, low_memory=False)
        df = df.rename(columns={c: c.strip() for c in df.columns})
        if "Label" not in df.columns:
            print(f"   ⚠ {p.name}: nema stupca 'Label', preskačem")
            continue
        df["Label"] = df["Label"].astype(str).str.strip()
        labele = sorted(df["Label"].unique())
        print(f"   ✓ {p.name}: {len(df):>9,} redova | {labele}")
        dfs.append(df)
    if not dfs:
        sys.exit("Nijedan CSV nije učitan.")
    return pd.concat(dfs, ignore_index=True)


def izgradi_split(
    df_all: pd.DataFrame,
) -> tuple[list[dict], list[dict], int, bool]:
    """
    Vraća (očišćeni test, neočišćeni test, broj duplikata, otisak se poklapa).

    CICIDS2017 sadrži retke s identičnim vektorom značajki. Takav redak može
    završiti i u treningu i u testu, pa model na testu prepoznaje primjer koji
    je već vidio. Split po indeksu to ne hvata — hvata ga tek usporedba samog
    ulaznog teksta, što se ovdje radi.
    """
    df_all = df_all.copy()
    df_all["_attack"] = df_all["Label"].map(lambda l: map_label(l)[0])

    records: list[dict] = []
    for attack, group in df_all.groupby("_attack"):
        if attack == "Unknown":
            continue
        n = min(len(group), SAMPLE_PER_CLASS)
        for _, row in group.sample(n=n, random_state=SEED).iterrows():
            atk, risk = map_label(row["Label"])
            records.append({
                "input":       build_input_text(row),
                "attack_type": atk,
                "risk_level":  risk,
                "raw_label":   str(row["Label"]).strip(),
            })

    random.seed(SEED)
    random.shuffle(records)

    # Koliko je od uzorkovanih primjera zapravo različito. CICIDS2017 za neke
    # napade bilježi tisuće gotovo jednakih tokova, pa 1200 uzorkovanih redaka
    # može sadržavati svega nekoliko desetaka različitih vektora značajki.
    # Model tada ne vidi 1200 primjera nego nekoliko desetaka, ponovljenih.
    print(f"\n   Ukupno primjera: {len(records):,}")
    print(f"     {'klasa':<14}{'uzorkovano':>12}{'različitih':>12}{'udio':>9}")
    razliciti_po_klasi = defaultdict(set)
    for r in records:
        razliciti_po_klasi[r["attack_type"]].add(r["input"])
    for k, v in sorted(Counter(r["attack_type"] for r in records).items()):
        d = len(razliciti_po_klasi[k])
        print(f"     {k:<14}{v:>12}{d:>12}{d / v * 100:>8.1f} %")

    by_class = defaultdict(list)
    for r in records:
        by_class[r["attack_type"]].append(r)

    train, val, test = [], [], []
    for _attack, items in by_class.items():
        random.seed(SEED)
        random.shuffle(items)
        n_tr = int(len(items) * 0.80)
        n_va = int(len(items) * 0.10)
        train += items[:n_tr]
        val   += items[n_tr:n_tr + n_va]
        test  += items[n_tr + n_va:]

    for lst in (train, val, test):
        random.shuffle(lst)

    print(f"\n   Train {len(train):,} | Validation {len(val):,} | Test {len(test):,}")

    # Otisak se računa PRIJE čišćenja, jer Colab duplikate nije uklanjao —
    # usporediv je samo neočišćeni split.
    otisak_ok = provjeri_otisak(test)

    u_treningu = {r["input"] for r in train}
    ocisceno = [r for r in test if r["input"] not in u_treningu]
    uklonjeno = len(test) - len(ocisceno)

    if uklonjeno:
        print(f"\n   Duplikati: {uklonjeno} od {len(test)} testnih primjera "
              f"({uklonjeno / len(test) * 100:.1f} %) ima vektor")
        print("   značajki identičan nekom primjeru iz treninga.")

        # Raspodjela po klasi pokazuje gdje je problem koncentriran — obično
        # kod napada koji generiraju mnogo gotovo jednakih kratkih tokova.
        po_klasi_uk = Counter(r["attack_type"] for r in test)
        po_klasi_dup = Counter(r["attack_type"] for r in test
                               if r["input"] in u_treningu)
        print(f"\n     {'klasa':<14}{'duplikata':>11}{'ukupno':>9}{'udio':>9}")
        for klasa in sorted(po_klasi_uk):
            d, uk = po_klasi_dup.get(klasa, 0), po_klasi_uk[klasa]
            print(f"     {klasa:<14}{d:>11}{uk:>9}{d / uk * 100:>8.1f} %")
    else:
        print("\n   Nema testnih primjera identičnih onima iz treninga.")

    return ocisceno, test, uklonjeno, otisak_ok


def provjeri_otisak(test: list[dict]) -> bool:
    """
    Uspoređuje raspodjelu klasa u prvih 200 testnih primjera s Colabovom.

    Ograničenje koje treba znati: ovo potvrđuje da se poklapa *struktura*
    splita — isti broj klasa, ista veličina, isti seed — ali ne dokazuje da su
    odabrani isti *retci*. Redci ovise o redoslijedu spajanja CSV datoteka.
    Za potpunu sigurnost koristi --test-json s izvozom testnog skupa iz Colaba.
    """
    stvarno = dict(Counter(r["attack_type"] for r in test[:200]))
    print("\n   Kontrolni zbroj (prvih 200 testnih primjera):")
    ok = stvarno == FINGERPRINT_V3
    for klasa in sorted(set(FINGERPRINT_V3) | set(stvarno)):
        oc = FINGERPRINT_V3.get(klasa, 0)
        st = stvarno.get(klasa, 0)
        znak = "✓" if oc == st else "✗"
        print(f"     {znak} {klasa:<14} Colab {oc:>3}   lokalno {st:>3}")
    return ok


def evaluiraj(model: str, test: list[dict], limit: int,
              greedy: bool = False) -> dict:
    uzorak = test[:limit]

    if greedy:
        # Colab je evaluirao s do_sample=False, dakle greedy. Ollama inače
        # uzorkuje (top_k 40, top_p 0.9), pa bi razlika u rezultatu djelomično
        # bila posljedica dekodiranja, a ne kvantizacije. Ovo ih izjednačuje.
        opcije = {"temperature": 0.0, "top_k": 1, "top_p": 1.0, "seed": SEED}
        nacin = "greedy (isto kao Colab)"
    else:
        opcije = {"temperature": 0.1}
        nacin = "uzorkovanje (T=0.1, Ollama zadano)"

    opcije |= {
        "num_predict": 220,
        "stop": ["### Instruction:", "### Input:", "### Response:"],
    }

    print(f"\n   Model: {model}   primjera: {len(uzorak)}")
    print(f"   Dekodiranje: {nacin}")
    print("   (prvi poziv uključuje učitavanje modela u memoriju)\n")

    atk_ok = risk_ok = parsed = neuspjeli = 0
    latencije: list[float] = []
    per_class = defaultdict(lambda: {"total": 0, "correct": 0})
    confusion: Counter = Counter()

    for i, item in enumerate(uzorak, 1):
        prompt = PROMPT_TEMPLATE.format(inp=item["input"])
        istina = item["attack_type"]
        per_class[istina]["total"] += 1

        t0 = time.perf_counter()
        odgovor = greska = None
        try:
            odgovor = ollama.generate(
                model=model, prompt=prompt, raw=True, options=opcije,
            )
        except Exception as exc:
            greska = exc
        ms = (time.perf_counter() - t0) * 1000
        # Prvi poziv uključuje učitavanje modela s diska i nije mjera inference.
        # Prekinuti poziv također nije mjera brzine pa se ne uračunava.
        if i > 1 and odgovor is not None:
            latencije.append(ms)

        if greska is not None:
            # Ollama povremeno prekine generiranje, primjerice kad dosegne
            # vlastitu granicu ponavljanja tokena. Takav se poziv bilježi kao
            # neuspješan odgovor, a ne pretvara tiho u predviđanje klase;
            # mjerenje se nastavlja da jedan tok ne sruši cijeli prolaz.
            neuspjeli += 1
            confusion[f"{istina}->POZIV_PREKINUT"] += 1
            print(f"   ! {i}/{len(uzorak)} poziv prekinut: {greska}")
            if i % 10 == 0 or i == len(uzorak):
                print(f"   {i:>4}/{len(uzorak)}  točnost "
                      f"{atk_ok / i * 100:5.1f} %  (zadnji poziv prekinut)")
            continue

        izvuceno = _extract_json(odgovor.get("response", ""))
        pred_atk = pred_risk = None
        if izvuceno:
            try:
                p = json.loads(izvuceno)
                parsed += 1
                pred_atk  = str(p.get("attack_type", "")).strip()
                pred_risk = str(p.get("risk_level", "")).strip().upper()
            except json.JSONDecodeError:
                pass

        if pred_atk == istina:
            atk_ok += 1
            per_class[istina]["correct"] += 1
        if pred_risk == item["risk_level"]:
            risk_ok += 1
        confusion[f"{istina}->{pred_atk or 'PARSE_FAIL'}"] += 1

        if i % 10 == 0 or i == len(uzorak):
            tocnost = atk_ok / i * 100
            print(f"   {i:>4}/{len(uzorak)}  točnost {tocnost:5.1f} %  "
                  f"({ms:.0f} ms zadnji)")

    n = len(uzorak)
    metrike = sastavi_metrike(model, n, atk_ok, risk_ok, parsed,
                              latencije, per_class, confusion)
    metrike["dekodiranje"] = nacin
    metrike["neuspjelih_poziva"] = neuspjeli
    if neuspjeli:
        print(f"\n   Prekinutih poziva: {neuspjeli} od {n} "
              f"({neuspjeli / n * 100:.1f} %) — bilježe se kao neuspješni.")
    return metrike


def sastavi_metrike(model, n, atk_ok, risk_ok, parsed,
                    latencije, per_class, confusion) -> dict:
    """Precision, recall i F1 po klasi + macro F1, računato iz confusion matrice."""
    klase = sorted({k.split("->")[0] for k in confusion})
    po_klasi = {}
    f1_ovi = []

    for klasa in klase:
        tp = confusion.get(f"{klasa}->{klasa}", 0)
        fn = sum(v for k, v in confusion.items()
                 if k.startswith(f"{klasa}->") and not k.endswith(f"->{klasa}"))
        fp = sum(v for k, v in confusion.items()
                 if k.endswith(f"->{klasa}") and not k.startswith(f"{klasa}->"))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec  = tp / (tp + fn) if tp + fn else 0.0
        f1   = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        f1_ovi.append(f1)
        po_klasi[klasa] = {
            "precision": round(prec, 4),
            "recall":    round(rec, 4),
            "f1":        round(f1, 4),
            "support":   per_class[klasa]["total"],
        }

    lat = sorted(latencije)
    def pct(p):
        return round(lat[int(len(lat) * p)], 1) if lat else None

    return {
        "model": model,
        "kvantizacija": "Q4_K_M (GGUF, Ollama, CPU)",
        "n_samples": n,
        "attack_type_accuracy_pct": round(atk_ok / n * 100, 1),
        "risk_level_accuracy_pct":  round(risk_ok / n * 100, 1),
        "macro_f1": round(sum(f1_ovi) / len(f1_ovi), 4) if f1_ovi else 0.0,
        "json_parse_pct": round(parsed / n * 100, 1),
        "latency_mean_ms": round(sum(lat) / len(lat), 1) if lat else None,
        "latency_p50_ms": pct(0.50),
        "latency_p95_ms": pct(0.95),
        "per_class": po_klasi,
        "confusion": dict(confusion.most_common()),
    }


def usporedi_s_colabom(metrike: dict, rezultati_dir: Path) -> None:
    """Ispisuje degradaciju u odnosu na 16-bitni rezultat iz Colaba."""
    kandidati = list(rezultati_dir.glob("report_*.json"))
    if not kandidati:
        print("\n   (nema report_*.json u rezultati/ — usporedba preskočena)")
        return

    kljuc = metrike["model"].split("-")[0].lower()
    izvor = next((p for p in kandidati if kljuc in p.name.lower()), None)
    if izvor is None:
        print("\n   (nije nađen odgovarajući report_*.json — usporedba preskočena)")
        return

    ref = json.loads(izvor.read_text(encoding="utf-8"))["evaluation"]
    print()
    print("═" * 70)
    print(f"USPOREDBA S COLABOM  ({izvor.name})")
    print("═" * 70)
    print(f"   {'':<26}{'fp16 / GPU':>14}{'Q4_K_M / CPU':>16}{'razlika':>12}")

    parovi = [
        ("Točnost tipa napada", "attack_type_accuracy_pct", "%"),
        ("Točnost rizika",      "risk_level_accuracy_pct",  "%"),
        ("JSON parse rate",     "json_parse_pct",           "%"),
    ]
    for naziv, kljuc_m, jed in parovi:
        a, b = ref.get(kljuc_m), metrike.get(kljuc_m)
        if a is None or b is None:
            continue
        print(f"   {naziv:<26}{a:>13.1f}{jed}{b:>15.1f}{jed}{b - a:>+11.1f}")

    a, b = ref.get("latency_mean_ms"), metrike.get("latency_mean_ms")
    if a and b:
        print(f"   {'Prosječna inferenca':<26}{a:>12.0f}ms{b:>14.0f}ms"
              f"{b / a:>10.2f}×")

    if ref.get("n_samples") != metrike["n_samples"]:
        print(f"\n   ⚠ Colab je mjeren na {ref.get('n_samples')} primjera, "
              f"ovdje ih je {metrike['n_samples']}.")
        print("     Za pošten broj u radu koristi isti broj primjera.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-dir", help="mapa s CICIDS2017 CSV datotekama")
    ap.add_argument("--csv", nargs="*", default=[], help="pojedinačne CSV datoteke")
    ap.add_argument("--test-json", help="testni skup izvezen iz Colaba (najtočnije)")
    ap.add_argument("--model", default=None, help="naziv modela u Ollami")
    ap.add_argument("--limit", type=int, default=200, help="broj testnih primjera")
    ap.add_argument("--svejedno", action="store_true",
                    help="nastavi i ako se kontrolni zbroj ne poklapa")
    ap.add_argument("--bez-ciscenja", action="store_true",
                    help="zadrži duplikate — mjeri na istom skupu kao Colab")
    ap.add_argument("--greedy", action="store_true",
                    help="greedy dekodiranje, isto kao Colab (do_sample=False)")
    args = ap.parse_args()

    if args.model is None:
        from app.core.config import CLASSIFIER_MODEL
        args.model = CLASSIFIER_MODEL

    print("\nNetlogRAG — evaluacija kvantiziranog modela")
    print("─" * 70)

    uklonjeno = 0

    if args.test_json:
        # Najpouzdaniji put: testni skup je doslovno onaj iz Colaba.
        print("1. UČITAVANJE TESTNOG SKUPA IZ COLABA")
        stavke = json.loads(Path(args.test_json).read_text(encoding="utf-8"))
        test = []
        for s in stavke:
            if "input" in s:
                test.append(s)
            else:
                # Format iz notebooka: cijeli trening tekst u polju "text".
                tekst = s["text"]
                ulaz = tekst.split("### Input:\n")[1].split("\n\n### Response:")[0]
                test.append({"input": ulaz,
                             "attack_type": s["attack_type"],
                             "risk_level":  s["risk_level"],
                             "raw_label":   s.get("raw_label", "")})
        print(f"   ✓ {len(test):,} primjera iz {Path(args.test_json).name}")
        print("   ✓ Split je po definiciji identičan Colabovom.")
        poklapa = True
    else:
        putanje = [Path(p) for p in args.csv]
        if args.csv_dir:
            putanje += sorted(Path(args.csv_dir).glob("*.csv"))
        if not putanje:
            sys.exit("Zadaj --csv-dir, --csv ili --test-json. Primjer:\n"
                     '  python scripts/evaluiraj_gguf.py --csv-dir "C:\\...\\CIC-IDS-2017"')

        print("1. UČITAVANJE CSV DATOTEKA")
        df_all = ucitaj_csvove(putanje)

        print("\n" + "─" * 70)
        print("2. REKONSTRUKCIJA TESTNOG SKUPA (seed 42, isto kao Colab)")
        test, test_neociscen, uklonjeno, poklapa = izgradi_split(df_all)

        if args.bez_ciscenja:
            # Mjeri se na istom skupu na kojem je mjeren i Colab, duplikatima
            # uključno. Jedina razlika prema Colabu ostaje kvantizacija, pa je
            # razlika u rezultatu čisti učinak kvantizacije.
            test = test_neociscen
            uklonjeno = 0
            print("\n   ⚠ --bez-ciscenja: duplikati ostaju u testnom skupu.")
            print("     Rezultat je izravno usporediv s Colabom, ali je kao i")
            print("     Colabov optimističan — ne prikazuj ga kao generalizaciju.")

    if not poklapa:
        print("\n   ✗ Split se NE poklapa s Colabom.")
        print("     Najčešći uzrok: učitan je drugačiji skup CSV datoteka ili")
        print("     drugačijim redoslijedom. Colab je koristio 5 datoteka koje")
        print("     zajedno daju 7 klasa po 1200 primjera:")
        print("       Tuesday (FTP/SSH-Patator), Wednesday (DoS),")
        print("       Thursday-Morning-WebAttacks, Friday-Afternoon-DDos,")
        print("       Friday-Afternoon-PortScan")
        print("     Zadaj ih izrijekom preko --csv tim redoslijedom.")
        if not args.svejedno:
            print("\n     Prekidam — rezultat ne bi bio usporediv.")
            print("     Ako svejedno želiš mjeriti, dodaj --svejedno.")
            sys.exit(1)
        print("\n   ⚠ Nastavljam na tvoj zahtjev. Rezultat NIJE usporediv s Colabom")
        print("     i ne smije se tako prikazati u radu.")

    print("\n" + "─" * 70)
    print("3. EVALUACIJA KROZ OLLAMU")
    metrike = evaluiraj(args.model, test, args.limit, greedy=args.greedy)
    metrike["split_identican_colabu"] = poklapa
    metrike["uklonjeno_duplikata"] = uklonjeno
    metrike["duplikati_uklonjeni"] = not args.bez_ciscenja
    metrike["izvor_testnog_skupa"] = (
        Path(args.test_json).name if args.test_json else "rekonstrukcija iz CSV-ova"
    )

    print("\n" + "═" * 70)
    print("REZULTAT")
    print("═" * 70)
    print(f"   Točnost tipa napada:  {metrike['attack_type_accuracy_pct']:.1f} %")
    print(f"   Točnost rizika:       {metrike['risk_level_accuracy_pct']:.1f} %")
    print(f"   Macro F1:             {metrike['macro_f1']:.4f}")
    print(f"   JSON parse rate:      {metrike['json_parse_pct']:.1f} %")
    if metrike["latency_mean_ms"]:
        print(f"   Inferenca (prosjek):  {metrike['latency_mean_ms']:.0f} ms")
        print(f"   Inferenca (p95):      {metrike['latency_p95_ms']:.0f} ms")

    print("\n   Po klasi:")
    print(f"     {'klasa':<14}{'P':>8}{'R':>8}{'F1':>8}{'n':>6}")
    for klasa, m in sorted(metrike["per_class"].items()):
        print(f"     {klasa:<14}{m['precision']:>8.3f}{m['recall']:>8.3f}"
              f"{m['f1']:>8.3f}{m['support']:>6}")

    rezultati_dir = Path(__file__).resolve().parent.parent / "rezultati"
    rezultati_dir.mkdir(exist_ok=True)
    usporedi_s_colabom(metrike, rezultati_dir)

    # Odvojena datoteka po varijanti — inače bi drugo mjerenje pregazilo prvo,
    # a upravo se ta dva broja uspoređuju.
    sufiks = "s_duplikatima" if args.bez_ciscenja else "ocisceno"
    if args.greedy:
        sufiks += "_greedy"
    izlaz = (rezultati_dir /
             f"gguf_evaluacija_{args.model.replace(':', '_')}_{sufiks}.json")
    izlaz.write_text(json.dumps(metrike, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print(f"\n   Spremljeno: {izlaz}")


if __name__ == "__main__":
    main()