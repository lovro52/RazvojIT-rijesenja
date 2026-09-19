#!/usr/bin/env python3
"""
XGBoost i Random Forest na istom splitu kao fine-tunani jezični modeli.

Zašto postoji
─────────────
Tvrdnja da jezični model nešto donosi ima smisla samo ako postoji referentna
točka. Ova skripta gradi tu točku, ali samo ako je usporedba poštena — a to
znači da klasični modeli moraju dobiti:

  • iste primjere za treniranje (isti seed, isti split po klasi),
  • isti ispitni skup, i očišćen i neočišćen,
  • iste vrijednosti značajki.

Zadnja stavka je suptilna. Jezični model ne vidi sirove stupce iz CSV-a nego
tekst oblika "TCP tok. FlowDuration=3.0, FwdPkts=1.0, ...", u kojem su brojevi
zaokruženi na jednu decimalu, a značajke s vrijednošću NaN ili beskonačno
izostavljene. Zato ova skripta značajke **parsira iz istog tog teksta**, umjesto
da ih čita iz CSV-a. Time oba pristupa dobivaju doslovno iste brojeve.

Pokretanje (isti argumenti kao evaluiraj_gguf.py):
    python scripts/baseline_usporedba.py --csv "...Tuesday..." "...Wednesday..." ...
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import numpy as np
    import pandas as pd
except ImportError:
    sys.exit("Nedostaju paketi. Instaliraj: pip install pandas numpy")

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import classification_report, f1_score
except ImportError:
    sys.exit("Nedostaje scikit-learn. Instaliraj: pip install scikit-learn")

try:
    from xgboost import XGBClassifier
except ImportError:
    sys.exit("Nedostaje xgboost. Instaliraj: pip install xgboost")

# Dijeli logiku s evaluiraj_gguf.py da se split ne može razići.
from evaluiraj_gguf import (
    FINGERPRINT_V3,
    FLOW_FEATURES,
    SAMPLE_PER_CLASS,
    SEED,
    build_input_text,
    map_label,
    ucitaj_csvove,
)

# Kratice koje se pojavljuju u tekstu — isti izraz kao u notebooku.
KRATICE = [
    (feat.replace("Total ", "").replace("Length of ", "Len")
         .replace("Packet", "Pkt").replace("Backward", "Bwd")
         .replace("Forward", "Fwd").replace(" ", ""))
    for feat in FLOW_FEATURES
]
PROTOKOLI = ["TCP", "UDP", "ICMP"]


def raspakiraj(ulaz: str) -> list[float]:
    """
    Iz teksta koji vidi jezični model vadi vektor značajki.

    "TCP tok. FlowDuration=3.0, FwdPkts=1.0, ..."  →  [3.0, 1.0, ..., proto]

    Značajka koju tekst ne sadrži (jer je bila NaN ili beskonačno) vraća se kao
    NaN, čime se čuva informacija da podatka nema — umjesto da se izmisli nula.
    """
    proto, _, ostatak = ulaz.partition(" tok. ")

    vrijednosti: dict[str, float] = {}
    for dio in ostatak.split(", "):
        kljuc, _, vrij = dio.partition("=")
        try:
            vrijednosti[kljuc] = float(vrij)
        except ValueError:
            continue

    vektor = [vrijednosti.get(k, np.nan) for k in KRATICE]
    # Protokol kao redni broj; nepoznat → -1.
    vektor.append(float(PROTOKOLI.index(proto)) if proto in PROTOKOLI else -1.0)
    return vektor


def izgradi_split(df_all: pd.DataFrame) -> tuple[list, list, list, bool]:
    """
    Ponavlja postupak iz notebooka i vraća (train, test_neociscen, test_ocisceno,
    otisak_se_poklapa). Isti seed i isti redoslijed kao evaluiraj_gguf.py.
    """
    df_all = df_all.copy()
    df_all["_attack"] = df_all["Label"].map(lambda l: map_label(l)[0])

    records = []
    for attack, group in df_all.groupby("_attack"):
        if attack == "Unknown":
            continue
        n = min(len(group), SAMPLE_PER_CLASS)
        for _, row in group.sample(n=n, random_state=SEED).iterrows():
            atk, _risk = map_label(row["Label"])
            records.append({"input": build_input_text(row), "attack_type": atk})

    random.seed(SEED)
    random.shuffle(records)

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
        val += items[n_tr:n_tr + n_va]
        test += items[n_tr + n_va:]

    for lst in (train, val, test):
        random.shuffle(lst)

    otisak = dict(Counter(r["attack_type"] for r in test[:200])) == FINGERPRINT_V3

    u_treningu = {r["input"] for r in train}
    ocisceno = [r for r in test if r["input"] not in u_treningu]

    print(f"   Train {len(train):,} | Validation {len(val):,} | Test {len(test):,}")
    print(f"   Očišćeni test: {len(ocisceno):,} "
          f"(uklonjeno {len(test) - len(ocisceno)})")
    return train, test, ocisceno, otisak


def u_matricu(zapisi: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    X = np.array([raspakiraj(r["input"]) for r in zapisi], dtype=float)
    y = np.array([r["attack_type"] for r in zapisi])
    return X, y


def izmjeri(naziv, model, X_tr, y_tr, X_te, y_te, klase) -> dict:
    print(f"\n   ── {naziv} ──")

    t0 = time.perf_counter()
    model.fit(X_tr, y_tr)
    trening_s = time.perf_counter() - t0
    print(f"   Trening: {trening_s:.1f} s")

    # Latencija po jednom toku, mjerena pojedinačno da bude usporediva s
    # jezičnim modelom, koji tokove obrađuje jedan po jedan.
    model.predict(X_te[:1])                       # zagrijavanje
    trajanja = []
    for i in range(min(200, len(X_te))):
        t0 = time.perf_counter()
        model.predict(X_te[i:i + 1])
        trajanja.append((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    y_pred = model.predict(X_te)
    ukupno_ms = (time.perf_counter() - t0) * 1000

    tocnost = float((y_pred == y_te).mean() * 100)
    macro = float(f1_score(y_te, y_pred, average="macro", labels=klase,
                           zero_division=0))

    print(f"   Točnost:  {tocnost:.1f} %")
    print(f"   Macro F1: {macro:.4f}")
    skupno_po_toku = ukupno_ms / len(X_te)
    print(f"   Latencija: {skupno_po_toku:.3f} ms/tok u nizu, "
          f"{np.mean(trajanja):.2f} ms po pojedinačnom pozivu")

    izvjestaj = classification_report(y_te, y_pred, labels=klase,
                                      output_dict=True, zero_division=0)
    print(f"\n     {'klasa':<14}{'P':>8}{'R':>8}{'F1':>8}{'n':>6}")
    for k in klase:
        m = izvjestaj.get(k)
        if not m:
            continue
        print(f"     {k:<14}{m['precision']:>8.3f}{m['recall']:>8.3f}"
              f"{m['f1-score']:>8.3f}{int(m['support']):>6}")

    return {
        "model": naziv,
        "attack_type_accuracy_pct": round(tocnost, 1),
        "macro_f1": round(macro, 4),
        "train_seconds": round(trening_s, 1),
        # Dvije različite veličine. Prva je stvarna cijena klasifikacije kad se
        # tokovi obrađuju skupno. Druga uključuje režiju pojedinačnog poziva,
        # koja kod Random Foresta nadmašuje sam izračun — usporediva je s
        # načinom na koji radi jezični model, ali nije mjera brzine modela.
        "latency_batch_ms_per_flow": round(float(skupno_po_toku), 4),
        "latency_single_call_ms": round(float(np.mean(trajanja)), 3),
        "latency_single_call_p95_ms": round(float(np.percentile(trajanja, 95)), 3),
        "per_class": {
            k: {
                "precision": round(izvjestaj[k]["precision"], 4),
                "recall": round(izvjestaj[k]["recall"], 4),
                "f1": round(izvjestaj[k]["f1-score"], 4),
                "support": int(izvjestaj[k]["support"]),
            }
            for k in klase if k in izvjestaj
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv-dir", help="mapa s CICIDS2017 CSV datotekama")
    ap.add_argument("--csv", nargs="*", default=[], help="pojedinačne datoteke")
    ap.add_argument("--svejedno", action="store_true",
                    help="nastavi i ako se kontrolni zbroj ne poklapa")
    args = ap.parse_args()

    putanje = [Path(p) for p in args.csv]
    if args.csv_dir:
        putanje += sorted(Path(args.csv_dir).glob("*.csv"))
    if not putanje:
        sys.exit("Zadaj --csv ili --csv-dir.")

    print("\nNetlogRAG — usporedni modeli na istom splitu")
    print("─" * 70)
    print("1. UČITAVANJE CSV DATOTEKA")
    df_all = ucitaj_csvove(putanje)

    print("\n" + "─" * 70)
    print("2. REKONSTRUKCIJA SPLITA (seed 42, isto kao jezični modeli)")
    train, test_sirovi, test_ocisceno, otisak = izgradi_split(df_all)

    if otisak:
        print("   ✓ Split je identičan onome na kojem su mjereni jezični modeli.")
    else:
        print("   ✗ Split se NE poklapa — vjerojatno drugačiji skup CSV datoteka.")
        if not args.svejedno:
            sys.exit("   Prekidam; rezultat ne bi bio usporediv.")

    X_tr, y_tr = u_matricu(train)
    klase = sorted(set(y_tr))
    print(f"   Značajki po primjeru: {X_tr.shape[1]} "
          f"({len(FLOW_FEATURES)} obilježja toka + protokol)")

    # Random Forest ne prihvaća nedostajuće vrijednosti, XGBoost ih obrađuje
    # sam. Imputacija se uči isključivo na skupu za treniranje.
    imputer = SimpleImputer(strategy="median").fit(X_tr)

    rezultati = {}
    for oznaka, zapisi in [("ocisceno", test_ocisceno),
                           ("s_duplikatima", test_sirovi[:200])]:
        print("\n" + "─" * 70)
        naslov = ("OČIŠĆEN ISPITNI SKUP" if oznaka == "ocisceno"
                  else "ISTIH 200 PRIMJERA, S DUPLIKATIMA")
        print(f"3. {naslov} — {len(zapisi)} primjera")

        X_te, y_te = u_matricu(zapisi)

        rf = RandomForestClassifier(n_estimators=300, random_state=SEED, n_jobs=-1)
        r1 = izmjeri("Random Forest", rf, imputer.transform(X_tr), y_tr,
                     imputer.transform(X_te), y_te, klase)

        # XGBoost traži cjelobrojne oznake klasa.
        idx = {k: i for i, k in enumerate(klase)}
        xgb = XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1,
                            tree_method="hist", random_state=SEED,
                            num_class=len(klase), objective="multi:softmax")

        class _Omot:
            """Vraća nazive klasa umjesto brojeva, da ispis bude jednak."""
            def __init__(self, m): self.m = m
            def fit(self, X, y):
                self.m.fit(X, np.array([idx[v] for v in y])); return self
            def predict(self, X):
                return np.array([klase[i] for i in self.m.predict(X)])

        r2 = izmjeri("XGBoost", _Omot(xgb), X_tr, y_tr, X_te, y_te, klase)
        rezultati[oznaka] = {"random_forest": r1, "xgboost": r2,
                             "n_samples": len(zapisi)}

    rezultati_dir = Path(__file__).resolve().parent.parent / "rezultati"
    rezultati_dir.mkdir(exist_ok=True)
    izlaz = rezultati_dir / "baseline_usporedba.json"
    izlaz.write_text(json.dumps(rezultati, ensure_ascii=False, indent=2),
                     encoding="utf-8")

    print("\n" + "═" * 70)
    print("ZA TABLICU U RADU (očišćen ispitni skup)")
    print("═" * 70)
    o = rezultati["ocisceno"]
    print(f"   {'Model':<18}{'Točnost':>10}{'Macro F1':>11}{'ms/tok':>12}")
    for r in (o["random_forest"], o["xgboost"]):
        print(f"   {r['model']:<18}{r['attack_type_accuracy_pct']:>9.1f}%"
              f"{r['macro_f1']:>11.4f}{r['latency_batch_ms_per_flow']:>12.4f}")
    print(f"   {'LLaMA 3.2 1B Q4':<18}{88.1:>9.1f}%{0.8821:>11.4f}{209.0:>12.1f}")
    print("\n   Latencija je ms po toku pri skupnoj obradi. Jezični model radi")
    print("   tok po tok, pa je njegova brojka i po jednom pozivu i skupno ista.")

    print(f"\n   Spremljeno: {izlaz}")


if __name__ == "__main__":
    main()