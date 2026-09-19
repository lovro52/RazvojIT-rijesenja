#!/usr/bin/env python3
"""
Dijagnostika fine-tunanog klasifikatora u Ollami.

Zašto postoji: `ollama run llama32-netlograg-v3 "TCP tok. FlowDuration=..."`
vraća engleski opis metrika umjesto JSON-a. To može imati dva vrlo različita
uzroka, a razlikuju se samo jednim testom:

  A) GGUF je ispravan, ali Modelfile TEMPLATE ne rekonstruira prompt iz
     treninga. Tada `ollama run` ne radi, a aplikacija radi — jer ona šalje
     `raw=True` i sama gradi puni prompt.

  B) GGUF nije fine-tunani model (merge adaptera nije uspio ili je
     konvertiran bazni model). Tada ni `raw=True` neće dati JSON.

Ovaj skript šalje prompt s `raw=True`, čime Modelfile potpuno izlazi iz igre.
Ako izlaz bude JSON → uzrok je A. Ako i dalje bude engleski tekst → uzrok je B.

Pokretanje iz korijena repozitorija:
    python scripts/test_klasifikator.py
    python scripts/test_klasifikator.py smollm2-netlograg-v3
    python scripts/test_klasifikator.py --all
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Omogućuje pokretanje iz korijena repozitorija bez instalacije paketa.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import ollama
except ImportError:
    sys.exit("Nedostaje paket 'ollama'. Instaliraj: pip install ollama")

from app.core.flow_schema import (
    INSTRUCTION,
    build_classification_prompt,
)
from app.services.llm_classifier import _extract_json

# ---------------------------------------------------------------------------
# Testni tokovi
#
# Tri toka s vrlo prepoznatljivim profilom. Nisu uzeti iz testnog skupa —
# svrha nije mjeriti točnost, nego provjeriti ponaša li se model uopće kao
# klasifikator. Zato se rezultat ovog skripta NE smije citirati u radu.
# ---------------------------------------------------------------------------
TEST_FLOWS: list[tuple[str, str, dict[str, float]]] = [
    (
        "PortScan (očekivano: PortScan / MEDIUM)",
        "TCP",
        {
            "Flow Duration": 3.0,
            "Total Fwd Packets": 1.0,
            "Total Backward Packets": 1.0,
            "Total Length of Fwd Packets": 0.0,
            "Total Length of Bwd Packets": 0.0,
            "Fwd Packet Length Mean": 0.0,
            "Bwd Packet Length Mean": 0.0,
            "Flow Bytes/s": 0.0,
            "Flow Packets/s": 666666.7,
            "Flow IAT Mean": 3.0,
            "Flow IAT Std": 0.0,
            "SYN Flag Count": 1.0,
            "PSH Flag Count": 0.0,
            "ACK Flag Count": 0.0,
            "Down/Up Ratio": 1.0,
            "Average Packet Size": 0.0,
        },
    ),
    (
        "SSH-Patator (očekivano: SSH-Patator / HIGH)",
        "TCP",
        {
            "Flow Duration": 4800000.0,
            "Total Fwd Packets": 16.0,
            "Total Backward Packets": 14.0,
            "Total Length of Fwd Packets": 1620.0,
            "Total Length of Bwd Packets": 2340.0,
            "Fwd Packet Length Mean": 101.3,
            "Bwd Packet Length Mean": 167.1,
            "Flow Bytes/s": 825.0,
            "Flow Packets/s": 6.3,
            "Flow IAT Mean": 165517.2,
            "Flow IAT Std": 402318.5,
            "SYN Flag Count": 0.0,
            "PSH Flag Count": 1.0,
            "ACK Flag Count": 1.0,
            "Down/Up Ratio": 1.0,
            "Average Packet Size": 132.0,
        },
    ),
    (
        "DDoS (očekivano: DDoS / HIGH)",
        "TCP",
        {
            "Flow Duration": 112.0,
            "Total Fwd Packets": 5.0,
            "Total Backward Packets": 0.0,
            "Total Length of Fwd Packets": 5840.0,
            "Total Length of Bwd Packets": 0.0,
            "Fwd Packet Length Mean": 1168.0,
            "Bwd Packet Length Mean": 0.0,
            "Flow Bytes/s": 52142857.0,
            "Flow Packets/s": 44642.9,
            "Flow IAT Mean": 28.0,
            "Flow IAT Std": 12.4,
            "SYN Flag Count": 0.0,
            "PSH Flag Count": 1.0,
            "ACK Flag Count": 0.0,
            "Down/Up Ratio": 0.0,
            "Average Packet Size": 1168.0,
        },
    ),
]

OPTIONS = {
    "temperature": 0.1,
    "num_predict": 220,
    "stop": ["### Instruction:", "### Input:", "### Response:"],
}


def provjeri_modelfile(model: str) -> bool:
    """
    Ispisuje registrirani TEMPLATE i provjerava sadrži li tekst instrukcije.

    Ako instrukcija nedostaje ili je dijakritika pokvarena (Modelfile spremljen
    kao ANSI umjesto UTF-8), `ollama run` nikad neće raditi — model dobiva
    rečenicu koju u treningu nije vidio.
    """
    print("─" * 70)
    print(f"1. MODELFILE PROVJERA — {model}")
    print("─" * 70)

    try:
        info = ollama.show(model)
    except Exception as exc:
        print(f"   ✗ Model nije registriran u Ollami: {exc}")
        return False

    template = (info.get("template") or "").strip()
    if not template:
        print("   ⚠ Model nema TEMPLATE. `ollama run` će slati goli prompt.")
    else:
        print("   Registrirani TEMPLATE:")
        for line in template.splitlines():
            print(f"     │ {line}")

    igla = INSTRUCTION[:40]
    if igla in template:
        print("\n   ✓ Instrukcija je u TEMPLATE-u i dijakritika je ispravna.")
        return True

    print("\n   ✗ Instrukcija NIJE pronađena u TEMPLATE-u.")
    print(f"     Traženo: {igla!r}")
    if "Analiziraj" in template:
        print("     Početak rečenice postoji, ali se ostatak razlikuje →")
        print("     najvjerojatnije kodiranje (Modelfile spremljen kao ANSI).")
        print("     Spremi Modelfile kao UTF-8 i ponovi `ollama create`.")
    else:
        print("     TEMPLATE uopće ne sadrži instrukciju iz treninga.")
    return False


def testiraj_model(model: str) -> dict[str, object]:
    """
    Šalje tri toka s raw=True i provjerava DVIJE stvari odvojeno:
    je li izlaz ispravan JSON i je li odgovor točan.

    Razlika je bitna. Model kojem je izvoz pukao i dalje zna vraćati
    besprijekoran JSON — samo u njemu uvijek piše ista klasa. Phi-3.5 je
    upravo tako prošao 3/3 po JSON-u, a 0/3 po točnosti, i na punoj
    evaluaciji ispao konstanta („DoS" za svaki tok, macro F1 0.047).
    Zato sam JSON nikad nije dokaz da je fine-tuning preživio konverziju.
    """
    print()
    print("─" * 70)
    print(f"2. GENERIRANJE (raw=True — Modelfile se zaobilazi) — {model}")
    print("─" * 70)

    uspjeha = 0
    tocnih = 0
    predikcije: list[str] = []
    trajanja: list[float] = []

    for naziv, proto, features in TEST_FLOWS:
        # Očekivana klasa je prvi token naziva, prije zagrade.
        ocekivano = naziv.split(" (")[0]
        print(f"\n   ▸ {naziv}")
        prompt = build_classification_prompt(features, proto)

        # Ispisuje se samo redak s ulazom — instrukcija je uvijek ista.
        ulaz = prompt.split("### Input:\n")[1].split("\n\n### Response:")[0]
        print(f"     Ulaz: {ulaz[:110]}{'…' if len(ulaz) > 110 else ''}")

        t0 = time.perf_counter()
        try:
            odgovor = ollama.generate(
                model=model, prompt=prompt, raw=True, options=OPTIONS
            )
        except Exception as exc:
            print(f"     ✗ Greška pri generiranju: {exc}")
            continue
        ms = (time.perf_counter() - t0) * 1000
        trajanja.append(ms)

        raw = odgovor.get("response", "")
        izvuceno = _extract_json(raw)

        if izvuceno is None:
            print(f"     ✗ Nema JSON objekta u izlazu  ({ms:.0f} ms)")
            print("     Sirovi izlaz (prvih 400 znakova):")
            for line in raw[:400].splitlines() or ["<prazno>"]:
                print(f"       │ {line}")
            continue

        try:
            payload = json.loads(izvuceno)
        except json.JSONDecodeError as exc:
            print(f"     ✗ Neispravan JSON: {exc}  ({ms:.0f} ms)")
            print(f"       │ {izvuceno[:300]}")
            continue

        uspjeha += 1
        predvideno = str(payload.get("attack_type"))
        predikcije.append(predvideno)

        if predvideno == ocekivano:
            tocnih += 1
            oznaka = "✓"
        else:
            oznaka = "✗"

        print(
            f"     {oznaka} attack_type={predvideno!r}  "
            f"risk_level={payload.get('risk_level')!r}  ({ms:.0f} ms)"
        )
        if predvideno != ocekivano:
            print(f"       ↳ očekivano {ocekivano!r} — JSON je ispravan, "
                  f"odgovor nije")

    prosjek = sum(trajanja) / len(trajanja) if trajanja else None
    return {"model": model, "json_ok": uspjeha, "tocnih": tocnih,
            "predikcije": predikcije, "ukupno": len(TEST_FLOWS),
            "prosjek_ms": prosjek}


def zakljucak(rezultat: dict[str, object], template_ok: bool) -> None:
    print()
    print("═" * 70)
    print("ZAKLJUČAK")
    print("═" * 70)

    ok = int(rezultat["json_ok"])
    tocnih = int(rezultat.get("tocnih", 0))
    predikcije = [str(p) for p in rezultat.get("predikcije", [])]  # type: ignore[union-attr]
    ukupno = int(rezultat["ukupno"])
    prosjek = rezultat["prosjek_ms"]

    print(f"   JSON odgovora: {ok}/{ukupno}")
    print(f"   Točnih klasa:  {tocnih}/{ukupno}")
    if prosjek:
        print(f"   Prosječna inferenca: {prosjek:.0f} ms")

    # Ispravan JSON s uvijek istom klasom je tipičan potpis pokvarenog
    # izvoza — vidi docstring funkcije testiraj_model.
    if len(predikcije) > 1 and len(set(predikcije)) == 1:
        print()
        print(f"   ✗ KOLAPS NA JEDNU KLASU — svih {len(predikcije)} odgovora "
              f"glasi {predikcije[0]!r}.")
        print("     Model vraća uredan JSON, ali ne gleda ulaz. Fine-tuning")
        print("     nije preživio konverziju u GGUF.")
        print()
        print("     Potvrdi na punoj evaluaciji:")
        print("       python scripts/evaluiraj_gguf.py --model <model> --limit 200")
        print("     Ako je ondje točnost jednaka udjelu najbrojnije klase u")
        print("     testnom skupu, model je konstanta. Dublja kvantizacija")
        print("     (Q8 umjesto Q4) to obično ne popravlja, ali vrijedi")
        print("     provjeriti radi usporedivosti s ostalim modelima.")
        return

    if ok == ukupno and tocnih == 0:
        print()
        print("   ✗ Format je ispravan, ali nijedan odgovor nije točan.")
        print("     Sam JSON nije dokaz da su fine-tunane težine u GGUF-u.")
        print("     Pokreni punu evaluaciju prije bilo kakvog zaključka.")
        return

    if ok == ukupno:
        print()
        print("   ✓ GGUF je upotrebljiv — fine-tuning je preživio konverziju.")
        print("     Aplikacija će raditi, jer `llm_classifier.py` šalje raw=True.")
        if tocnih < ukupno:
            print()
            print(f"     Napomena: {ukupno - tocnih} od {ukupno} odgovora nije "
                  f"točan. Tri")
            print("     sintetička toka nisu mjerenje — pravi broj daje tek")
            print("     `evaluiraj_gguf.py` na 200 primjera.")
        if not template_ok:
            print()
            print("     `ollama run` i dalje neće raditi dok se ne popravi")
            print("     TEMPLATE u Modelfileu — ali to je samo udobnost za")
            print("     ručno testiranje, ne utječe na aplikaciju.")
        return

    if ok == 0:
        print()
        print("   ✗ GGUF se ponaša kao BAZNI model. Fine-tuning nije u težinama.")
        print()
        print("   Provjeri redom:")
        print("     1. Je li GGUF nastao iz SPOJENOG modela (base + LoRA adapter),")
        print("        a ne iz baznog? U notebooku je to")
        print("        `model.save_pretrained_merged(..., save_method='merged_16bit')`")
        print("        prije konverzije. Ako je spremljen samo adapter, GGUF")
        print("        sadrži bazne težine.")
        print("     2. Je li `ollama create` pokrenut NAKON zadnje izmjene")
        print("        Modelfilea i pokazuje li FROM na točan .gguf?")
        print("        `ollama rm <model>` pa ponovni `ollama create` isključuje")
        print("        zastarjeli sloj u cacheu.")
        print("     3. Je li veličina .gguf datoteke očekivana za taj model?")
        print("        Adapter sam je nekoliko desetaka MB — ako je datoteka")
        print("        toliko mala, merge nije napravljen.")
        return

    print()
    print(f"   ⚠ Djelomično ({ok}/{ukupno}). Težine su fine-tunane, ali izlaz")
    print("     nije stabilan. Najčešće je uzrok `num_predict` premalen ili")
    print("     nedostaju `stop` sekvence, pa se JSON presiječe.")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    svi = "--all" in sys.argv

    if svi:
        # "id" je naziv pod kojim je model registriran u Ollami;
        # "name" je samo prikazno ime za sučelje.
        from app.core.config import FINETUNED_MODELS
        modeli = [m["id"] for m in FINETUNED_MODELS]
    elif args:
        modeli = args
    else:
        from app.core.config import CLASSIFIER_MODEL
        modeli = [CLASSIFIER_MODEL]

    print()
    print("NetlogRAG — dijagnostika fine-tunanog klasifikatora")
    print(f"Instrukcija iz sheme: {INSTRUCTION}")
    print()

    for model in modeli:
        template_ok = provjeri_modelfile(model)
        rezultat = testiraj_model(model)
        zakljucak(rezultat, template_ok)
        print()


if __name__ == "__main__":
    main()
