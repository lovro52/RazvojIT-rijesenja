"""
Test korisničkog prihvaćanja (UAT) aplikacije NetlogRAG — automatizirani dio.

Skripta pokreće zasebnu instancu poslužitelja u izdvojenom ispitnom okruženju
(vlastita mapa za učitane datoteke, vektorsku bazu i SQLite), izvodi scenarije
kroz sučelje za programiranje aplikacije i za svaki bilježi stvarni rezultat,
status i vrijeme izvođenja. Postojeći podaci u mapi data/ se ne diraju.

Pokretanje iz korijena projekta (s aktiviranim virtualnim okruženjem):

    python scripts/uat_netlograg.py --tester "T1 (autor)"

Preduvjeti: Ollama radi i u njoj su registrirani opći model (OLLAMA_MODEL, zadano
llama3.1:8b) i prilagođeni klasifikator (CLASSIFIER_MODEL, zadano
llama32-netlograg-v3); u data/uploads postoji barem jedna datoteka skupa
CICIDS2017 (ili se putanja zada s --cicids).

Rezultati: rezultati/uat_rezultati.json i rezultati/uat_rezultati.md
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

PROJEKT = Path(__file__).resolve().parent.parent
KLASE = {"BENIGN", "DDoS", "DoS", "FTP-Patator", "PortScan", "SSH-Patator", "WebAttack"}
RIZICI = {"LOW", "MEDIUM", "HIGH"}
PITANJE_EN = "Is there any brute force or login attack attempt?"   # "Pokušava li netko provaliti?"
PITANJE_HR = "Pokušava li netko provaliti?"

# ─────────────────────────────────────────────────────────────────────────────
# HTTP pomoćne funkcije (samo standardna biblioteka)
# ─────────────────────────────────────────────────────────────────────────────
BASE = ""


def zahtjev(metoda: str, putanja: str, params: dict | None = None,
            datoteka: tuple[str, bytes] | None = None, timeout: int = 900):
    url = BASE + putanja
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = None
    headers = {}
    if datoteka is not None:
        granica = uuid.uuid4().hex
        ime, sadrzaj = datoteka
        data = (
            f"--{granica}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{ime}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + sadrzaj + f"\r\n--{granica}--\r\n".encode()
        headers["Content-Type"] = f"multipart/form-data; boundary={granica}"
    req = urllib.request.Request(url, data=data, method=metoda, headers=headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            tijelo = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        tijelo = e.read()
        status = e.code
    ms = round((time.perf_counter() - t0) * 1000)
    try:
        js = json.loads(tijelo.decode("utf-8"))
    except Exception:
        js = {"_sirovo": tijelo[:500].decode("utf-8", "replace")}
    return status, js, ms


# ─────────────────────────────────────────────────────────────────────────────
# Evidencija scenarija
# ─────────────────────────────────────────────────────────────────────────────
REZULTATI: list[dict] = []
KONTEKST: dict = {}


def scenarij(sid, cjelina, vrsta, naziv, preduvjeti, koraci, ocekivano):
    def omotac(fn):
        def izvedi():
            pocetak = datetime.now()
            print(f"[{sid}] {naziv} ... ", end="", flush=True)
            try:
                stvarno, prosao, napomena = fn()
            except Exception as e:  # noqa: BLE001
                stvarno = f"Iznimka u testu: {e.__class__.__name__}: {e}"
                prosao, napomena = False, traceback.format_exc(limit=2)
            trajanje = round((datetime.now() - pocetak).total_seconds(), 1)
            REZULTATI.append({
                "id": sid, "cjelina": cjelina, "vrsta": vrsta, "scenarij": naziv,
                "preduvjeti": preduvjeti, "koraci": koraci, "ocekivano": ocekivano,
                "stvarno": stvarno, "status": "Prošao" if prosao else "Nije prošao",
                "napomena": napomena, "izvedeno": pocetak.isoformat(timespec="seconds"),
                "trajanje_s": trajanje,
            })
            print("PROŠAO" if prosao else "NIJE PROŠAO", f"({trajanje} s)")
        izvedi.sid = sid
        return izvedi
    return omotac


# ─────────────────────────────────────────────────────────────────────────────
# Ispitni podaci
# ─────────────────────────────────────────────────────────────────────────────
VLASTITI_CSV = (
    "timestamp,src_ip,dst_ip,src_port,dst_port,protocol,bytes,flag\n"
    "2026-01-21T10:00:00Z,192.168.0.10,10.0.0.5,51512,80,TCP,450,SYN\n"
    "2026-01-21T10:00:01Z,192.168.0.10,10.0.0.5,51513,80,TCP,460,SYN\n"
    "2026-01-21T10:00:02Z,203.0.113.77,10.0.0.5,44444,22,TCP,1200,PSH\n"
    "2026-01-21T10:00:03Z,203.0.113.77,10.0.0.5,44445,22,TCP,1300,PSH\n"
    "2026-01-21T10:00:04Z,198.51.100.9,10.0.0.5,60000,443,TCP,900,ACK\n"
)


def pripremi_podatke(cicids: Path, mapa: Path) -> dict:
    import pandas as pd
    mapa.mkdir(parents=True, exist_ok=True)
    p = {}
    p["vlastiti"] = mapa / "uat_vlastiti_format.csv"
    p["vlastiti"].write_text(VLASTITI_CSV, encoding="utf-8")

    df = pd.read_csv(cicids, nrows=40, low_memory=False, encoding="latin-1")
    stupac = next(c for c in df.columns if c.strip() == "Flow Bytes/s")
    df[stupac] = df[stupac].astype("float64")
    df.loc[0, stupac] = float("inf")
    df.loc[1, stupac] = float("nan")
    p["rubni"] = mapa / "uat_cicids_inf_nan.csv"
    df.to_csv(p["rubni"], index=False)
    KONTEKST["rubni_label"] = str(df.iloc[0][next(c for c in df.columns if c.strip() == "Label")]).strip()

    p["txt"] = mapa / "uat_nije_csv.txt"
    p["txt"].write_text("ovo nije CSV datoteka\n", encoding="utf-8")
    p["neispravan"] = mapa / "uat_neispravan.csv"
    p["neispravan"].write_text('a,b\n1,2,3,4\n5,6,7,8,9\n', encoding="utf-8")
    p["prazan"] = mapa / "uat_prazan.csv"
    p["prazan"].write_bytes(b"")
    return p


def ucitaj(putanja: Path, ime: str | None = None):
    return zahtjev("POST", "/logs/upload", datoteka=(ime or putanja.name, putanja.read_bytes()))


# ─────────────────────────────────────────────────────────────────────────────
# Scenariji
# ─────────────────────────────────────────────────────────────────────────────
C1, C2, C3, C4, C5 = ("Učitavanje i normalizacija", "Indeksiranje i pretraživanje",
                      "Klasifikacija", "Postavljanje pitanja i prikaz odgovora",
                      "Povijest i izvoz izvještaja")


@scenarij("UAT-P-01", C4, "rubni", "Pitanje nad praznim indeksom",
          "Ispitno okruženje tek je pokrenuto; nijedna datoteka nije indeksirana.",
          "Postaviti pitanje (način auto, top 5).",
          "Sustav ne navodi zapise koji ne postoje: izvještaj bez dokaza ili jasna poruka da dokaza nema.")
def t_prazan_indeks():
    s, js, ms = zahtjev("GET", "/logs/query/rag_local_mode", {"q": PITANJE_EN, "top_k": 5, "mode": "auto"})
    if s != 200:
        return f"HTTP {s}: {str(js)[:200]}", False, "Upit nad praznim indeksom završava pogreškom poslužitelja."
    ev = js.get("evidence", [])
    rep = js.get("report", {})
    hl = [h.get("id") for h in rep.get("evidence_highlights", []) if isinstance(h, dict)]
    stvarno = (f"HTTP 200 za {ms} ms; dohvaćeno dokaza: {len(ev)}; razina rizika: {rep.get('risk_level')}; "
               f"istaknuti dokazi: {hl or 'nema'}")
    izmisljeni = [h for h in hl if h]
    if izmisljeni:
        return stvarno, False, "Model navodi identifikatore zapisa kojih u bazi nema (potvrđuje ograničenje iz odjeljka 9.1)."
    return stvarno, True, "Bez izmišljenih identifikatora."


@scenarij("UAT-U-01", C1, "uspješan", "Učitavanje datoteke skupa CICIDS2017",
          "Poslužitelj radi; datoteka skupa CICIDS2017 dostupna lokalno.",
          "Učitati datoteku kroz /logs/upload.",
          "HTTP 200; datoteka spremljena pod nazivom s vremenskom oznakom; prijavljeni broj redaka i stupaca odgovara datoteci.")
def t_upload_cicids():
    import pandas as pd
    cic: Path = KONTEKST["cicids"]
    ocek_redaka = len(pd.read_csv(cic, low_memory=False, encoding="latin-1", usecols=[0]))
    s, js, ms = ucitaj(cic)
    KONTEKST["cicids_ime"] = js.get("filename")
    stvarno = f"HTTP {s} za {ms} ms; naziv {js.get('filename')}; redaka {js.get('rows')}; stupaca {len(js.get('columns', []))}"
    ok = s == 200 and js.get("rows") == ocek_redaka and str(js.get("filename", "")).endswith(cic.name.replace(" ", "_"))
    return stvarno, ok, f"Očekivani broj redaka: {ocek_redaka}."


@scenarij("UAT-U-02", C1, "uspješan", "Normalizacija zapisa bez curenja oznake",
          "UAT-U-01 prošao.",
          "Pozvati /logs/normalize za učitanu datoteku i pregledati uzorak zapisa.",
          "Najviše 5000 zapisa; oznaka klase (Label) nije u tekstualnom opisu zapisa nego u zasebnom polju.")
def t_normalize():
    s, js, ms = zahtjev("POST", "/logs/normalize", {"filename": KONTEKST["cicids_ime"]})
    uzorak = js.get("sample", [])
    procurilo = [r for r in uzorak if r.get("ground_truth") and r["ground_truth"] in (r.get("message") or "")]
    imaju_gt = sum(1 for r in uzorak if r.get("ground_truth"))
    stvarno = (f"HTTP {s} za {ms} ms; normaliziranih zapisa {js.get('records_count')}; u uzorku od {len(uzorak)} "
               f"zapisa oznaka u zasebnom polju: {imaju_gt}, oznaka u opisu: {len(procurilo)}")
    ok = s == 200 and 0 < js.get("records_count", 0) <= 5000 and not procurilo and imaju_gt == len(uzorak)
    return stvarno, ok, ""


@scenarij("UAT-U-03", C1, "rubni", "Vlastiti format zapisa s nazivom protokola",
          "Poslužitelj radi.",
          "Učitati CSV s pet zapisa u kojem je protokol zapisan nazivom (TCP) i normalizirati ga.",
          "HTTP 200; svih pet zapisa normalizirano; protokol prepoznat kao TCP.")
def t_vlastiti():
    s, js, _ = ucitaj(KONTEKST["podaci"]["vlastiti"])
    KONTEKST["vlastiti_ime"] = js.get("filename")
    s2, js2, ms = zahtjev("POST", "/logs/normalize", {"filename": KONTEKST["vlastiti_ime"]})
    prot = sorted({r.get("protocol") for r in js2.get("sample", [])})
    stvarno = f"učitavanje HTTP {s}; normalizacija HTTP {s2}; zapisa {js2.get('records_count')}; protokoli {prot}"
    return stvarno, s == 200 and s2 == 200 and js2.get("records_count") == 5 and prot == ["TCP"], ""


@scenarij("UAT-U-04", C1, "rubni", "Beskonačne i nedostajuće vrijednosti obilježja",
          "Poslužitelj radi.",
          "Učitati isječak od 40 zapisa CICIDS2017 u kojem je Flow Bytes/s u prvom zapisu beskonačan, a u drugom prazan; normalizirati.",
          "HTTP 200; zapisi se normaliziraju; beskonačna i nedostajuća vrijednost izostavljene su iz opisa i obilježja toka.")
def t_inf_nan():
    s, js, _ = ucitaj(KONTEKST["podaci"]["rubni"])
    ime = js.get("filename")
    if not ime:  # odgovor nije stigao, ali datoteka je možda spremljena — potraži je u popisu
        _, fl, _ = zahtjev("GET", "/logs/files")
        imena = sorted(f["filename"] for f in fl.get("files", []) if f.get("filename", "").endswith("uat_cicids_inf_nan.csv"))
        ime = imena[-1] if imena else None
    KONTEKST["rubni_ime"] = ime
    s2, js2, _ = zahtjev("POST", "/logs/normalize", {"filename": KONTEKST["rubni_ime"]})
    uz = js2.get("sample", [])
    r0, r1 = (uz + [{}, {}])[:2]
    f0 = (r0.get("flow_features") or {}).get("Flow Bytes/s", "izostavljeno")
    f1 = (r1.get("flow_features") or {}).get("Flow Bytes/s", "izostavljeno")
    losi = [x for x in ("inf", "nan") if x in (r0.get("message", "") + r1.get("message", "")).lower()]
    stvarno = (f"učitavanje HTTP {s}; normalizacija HTTP {s2}; zapisa {js2.get('records_count')}; "
               f"Flow Bytes/s u 1. zapisu: {f0}, u 2. zapisu: {f1}; 'inf'/'nan' u opisu: {losi or 'ne'}")
    ok = s == 200 and s2 == 200 and f0 == "izostavljeno" and f1 == "izostavljeno" and not losi
    napomena = "Normalizacija uzorkuje zapise samo iznad 5000, pa je redoslijed prvih zapisa sačuvan."
    if s != 200:
        napomena = (f"Učitavanje je vratilo HTTP {s}: {str(js)[:120]}. Datoteka je spremljena, a normalizacija "
                    f"{'je ispravno izostavila vrijednosti' if s2 == 200 and f0 == f1 == 'izostavljeno' and not losi else 'nije uspjela'}.")
    return stvarno, ok, napomena


@scenarij("UAT-U-05", C1, "neuspješan", "Datoteka koja nije CSV",
          "Poslužitelj radi.", "Učitati tekstualnu datoteku s nastavkom .txt.",
          "Zahtjev se odbija (HTTP 400) s porukom da su dopuštene samo datoteke CSV.")
def t_txt():
    s, js, _ = ucitaj(KONTEKST["podaci"]["txt"])
    return f"HTTP {s}: {js.get('detail')}", s == 400, ""


@scenarij("UAT-U-06", C1, "neuspješan", "Neispravno oblikovan CSV",
          "Poslužitelj radi.", "Učitati CSV u kojem reci imaju više stupaca od zaglavlja.",
          "Zahtjev se odbija (HTTP 400) s porukom da se CSV ne može pročitati; poslužitelj nastavlja raditi.")
def t_neispravan():
    s, js, _ = ucitaj(KONTEKST["podaci"]["neispravan"])
    s2, _, _ = zahtjev("GET", "/health")
    return f"HTTP {s}: {str(js.get('detail'))[:120]}; /health nakon toga: HTTP {s2}", s == 400 and s2 == 200, ""


@scenarij("UAT-U-07", C1, "rubni", "Prazna CSV datoteka",
          "Poslužitelj radi.", "Učitati praznu datoteku s nastavkom .csv.",
          "Zahtjev se odbija (HTTP 400) s razumljivom porukom.")
def t_prazan():
    s, js, _ = ucitaj(KONTEKST["podaci"]["prazan"])
    return f"HTTP {s}: {str(js.get('detail'))[:120]}", s == 400, ""


@scenarij("UAT-I-01", C2, "uspješan", "Indeksiranje datoteke iznad granice od 5000 zapisa",
          "UAT-U-01 prošao.", "Pozvati /logs/index (bez automatske analize).",
          "HTTP 200; indeksirano točno 5000 zapisa; datoteka označena kao indeksirana.")
def t_index_veliki():
    s, js, ms = zahtjev("POST", "/logs/index", {"filename": KONTEKST["cicids_ime"], "auto_analyze": "false"})
    _, fl, _ = zahtjev("GET", "/logs/files")
    ozn = [f for f in fl.get("files", []) if f.get("filename") == KONTEKST["cicids_ime"]]
    ind = bool(ozn and ozn[0].get("indexed"))
    stvarno = f"HTTP {s} za {ms / 1000:.1f} s; indeksirano {js.get('indexed_records')}; oznaka indeksiranja u popisu datoteka: {ind}"
    return stvarno, s == 200 and js.get("indexed_records") == 5000 and ind, ""


@scenarij("UAT-I-02", C2, "rubni", "Indeksiranje datoteke ispod granice",
          "UAT-U-03 prošao.", "Indeksirati datoteku s pet zapisa.",
          "HTTP 200; indeksirano svih pet zapisa.")
def t_index_mali():
    s, js, ms = zahtjev("POST", "/logs/index", {"filename": KONTEKST["vlastiti_ime"], "auto_analyze": "false"})
    return f"HTTP {s} za {ms} ms; indeksirano {js.get('indexed_records')}", s == 200 and js.get("indexed_records") == 5, ""


@scenarij("UAT-I-03", C2, "rubni", "Zapisi bez adresa, portova i vremenske oznake",
          "Datoteka iz UAT-U-04 spremljena; datoteka skupa CICIDS2017 ne sadrži izvorišnu adresu ni vremensku oznaku.",
          "Indeksirati isječak od 40 zapisa.",
          "HTTP 200; svi zapisi indeksirani unatoč nedostajućim metapodacima.")
def t_index_bez_meta():
    s, js, ms = zahtjev("POST", "/logs/index", {"filename": KONTEKST["rubni_ime"], "auto_analyze": "false"})
    return f"HTTP {s} za {ms} ms; indeksirano {js.get('indexed_records')}", s == 200 and js.get("indexed_records") == 40, ""


@scenarij("UAT-I-04", C2, "uspješan", "Semantička pretraga",
          "UAT-I-01 prošao.", "Pretražiti indeks upitom o pokušajima provale (top 5).",
          "HTTP 200; pet rezultata, svaki s tekstom zapisa, metapodacima i udaljenošću.")
def t_semanticka():
    s, js, ms = zahtjev("GET", "/logs/query/semantic", {"q": PITANJE_EN, "top_k": 5})
    rez = js.get("results", [])
    potpuni = sum(1 for r in rez if r.get("document") and r.get("distance") is not None and r.get("metadata") is not None)
    return f"HTTP {s} za {ms} ms; rezultata {len(rez)}, potpunih {potpuni}", s == 200 and len(rez) == 5 and potpuni == 5, ""


@scenarij("UAT-I-05", C2, "uspješan", "Usporedba pretrage po ključnim riječima i semantičke pretrage",
          "UAT-I-01 prošao.", "Pozvati /logs/compare s upitom 'port scan'.",
          "HTTP 200; oba načina vraćaju rezultate i izmjereno vrijeme.")
def t_compare():
    s, js, ms = zahtjev("GET", "/logs/compare", {"q": "port scan", "top_k": 5})
    kw, se = js.get("keyword", {}), js.get("semantic", {})
    stvarno = (f"HTTP {s} za {ms} ms; ključne riječi: {kw.get('count')} rezultata za {kw.get('time_ms')} ms; "
               f"semantička: {se.get('count')} rezultata za {se.get('time_ms')} ms")
    return stvarno, s == 200 and se.get("count") == 5 and kw.get("time_ms") is not None, \
        "Pretraga po ključnim riječima traži doslovno podudaranje, pa može vratiti i nula rezultata."


@scenarij("UAT-I-06", C2, "uspješan", "Filtriranje zapisa po protokolu",
          "UAT-I-02 prošao.", "Pozvati /logs/filter s protokolom TCP.",
          "HTTP 200; vraćeni su samo zapisi s protokolom TCP.")
def t_filter():
    s, js, ms = zahtjev("GET", "/logs/filter", {"protocol": "TCP"})
    rec = js.get("records", [])
    krivi = [r for r in rec if str(r.get("protocol", "")).upper() != "TCP"]
    return f"HTTP {s} za {ms} ms; zapisa {js.get('count')}, s drugim protokolom {len(krivi)}", \
        s == 200 and len(rec) > 0 and not krivi, ""


@scenarij("UAT-I-07", C2, "neuspješan", "Indeksiranje nepostojeće datoteke",
          "Poslužitelj radi.", "Pozvati /logs/index s nazivom koji ne postoji.",
          "HTTP 404 s porukom da datoteka nije pronađena.")
def t_index_404():
    s, js, _ = zahtjev("POST", "/logs/index", {"filename": "ne_postoji.csv", "auto_analyze": "false"})
    return f"HTTP {s}: {js.get('detail')}", s == 404, ""


@scenarij("UAT-K-01", C3, "uspješan", "Dostupnost prilagođenog modela",
          "Ollama radi.", "Pozvati /logs/classifier/models.",
          "Zadani klasifikacijski model naveden je kao instaliran.")
def t_modeli():
    s, js, _ = zahtjev("GET", "/logs/classifier/models")
    zad = js.get("default")
    inst = [m["id"] for m in js.get("models", []) if m.get("installed")]
    return f"HTTP {s}; zadani model {zad}; instalirani {inst}", s == 200 and zad in inst, ""


@scenarij("UAT-K-02", C3, "uspješan", "Klasifikacija deset tokova",
          "UAT-U-01 i UAT-K-01 prošli.", "Pozvati /logs/classifier/classify za deset tokova.",
          "Svih deset tokova klasificirano u jednu od sedam klasa i jednu od tri razine rizika, uz izmjereno vrijeme.")
def t_klasifikacija():
    s, js, ms = zahtjev("POST", "/logs/classifier/classify", {"filename": KONTEKST["cicids_ime"], "limit": 10})
    rez = js.get("results", [])
    valjani = [r for r in rez if r.get("attack_type") in KLASE and r.get("risk_level") in RIZICI]
    stvarno = (f"HTTP {s} za {ms / 1000:.1f} s; klasificirano {js.get('classified')}, neuspjelih {js.get('failed')}, "
               f"valjanih oznaka {len(valjani)}; prosjek {js.get('avg_inference_ms')} ms po toku; "
               f"podudarnost s istinitom oznakom {js.get('accuracy_vs_ground_truth')} % na {js.get('comparable_records')} tokova")
    return stvarno, s == 200 and len(valjani) == 10, \
        "Točnost na deset tokova nije mjera kvalitete modela (vidi poglavlje 8); provjerava se samo ispravnost rada."


@scenarij("UAT-K-03", C3, "rubni", "Datoteka bez obilježja toka",
          "UAT-U-03 prošao.", "Pokušati klasifikaciju datoteke vlastitog formata (bez obilježja CICIDS2017).",
          "HTTP 400 s porukom da datoteka nema obilježja toka potrebna za klasifikaciju.")
def t_bez_obiljezja():
    s, js, _ = zahtjev("POST", "/logs/classifier/classify", {"filename": KONTEKST["vlastiti_ime"], "limit": 5})
    return f"HTTP {s}: {js.get('detail')}", s == 400, ""


@scenarij("UAT-K-04", C3, "neuspješan", "Nepostojeći klasifikacijski model",
          "UAT-U-01 prošao.", "Pokrenuti klasifikaciju pet tokova s modelom koji nije registriran u Ollami.",
          "Zahtjev se odbija s porukom o nedostupnom modelu ili se svi tokovi vraćaju kao neuspješni; nema izmišljenih oznaka.")
def t_krivi_model():
    s, js, ms = zahtjev("POST", "/logs/classifier/classify",
                        {"filename": KONTEKST["cicids_ime"], "limit": 5, "model": "ne-postoji-model"})
    if s == 200:
        stvarno = f"HTTP 200 za {ms} ms; klasificirano {js.get('classified')}, neuspjelih {js.get('failed')}"
        return stvarno, js.get("classified") == 0, \
            "Poslužitelj ne javlja pogrešku nego vraća prazan rezultat; korisnik vidi samo broj neuspjelih tokova."
    return f"HTTP {s}: {str(js.get('detail'))[:150]}", s in (400, 404, 503), ""


@scenarij("UAT-K-05", C3, "neuspješan", "Klasifikacija nepostojeće datoteke",
          "Poslužitelj radi.", "Pozvati klasifikaciju s nazivom datoteke koja ne postoji.",
          "HTTP 404 s porukom da datoteka nije pronađena.")
def t_klas_404():
    s, js, _ = zahtjev("POST", "/logs/classifier/classify", {"filename": "ne_postoji.csv", "limit": 5})
    return f"HTTP {s}: {js.get('detail')}", s == 404, ""


@scenarij("UAT-K-06", C3, "uspješan", "Klasifikator i sloj dohvata na istom toku",
          "UAT-I-01 i UAT-K-01 prošli.", "Pozvati /logs/classifier/compare_rag za prvi tok datoteke.",
          "Oba sloja vraćaju rezultat; klasifikator vraća tip napada i razinu rizika, sloj dohvata izvještaj s brojem dokaza.")
def t_compare_rag():
    s, js, ms = zahtjev("POST", "/logs/classifier/compare_rag", {"filename": KONTEKST["cicids_ime"], "row_index": 0})
    k, r = js.get("classifier", {}), js.get("rag", {})
    stvarno = (f"HTTP {s} za {ms / 1000:.1f} s; klasifikator: {k.get('attack_type')}/{k.get('risk_level')} za "
               f"{k.get('inference_ms')} ms; dohvat i generiranje: rizik {r.get('risk_level')}, dokaza "
               f"{r.get('evidence_count')}, {r.get('inference_ms')} ms; istinita oznaka {js.get('flow', {}).get('ground_truth')}")
    return stvarno, s == 200 and k.get("attack_type") in KLASE and r.get("evidence_count", 0) > 0, ""


def _provjeri_izvjestaj(js):
    rep = js.get("report", {})
    ev = js.get("evidence", [])
    ids = {e.get("id") for e in ev}
    hl = [h.get("id") for h in rep.get("evidence_highlights", []) if isinstance(h, dict)]
    izmisljeni = [h for h in hl if h not in ids]
    polja = all(rep.get(k) for k in ("risk_level", "summary")) and isinstance(rep.get("recommended_actions"), list)
    return rep, ev, hl, izmisljeni, polja


@scenarij("UAT-P-02", C4, "uspješan", "Pitanje iz predloška",
          "Indeksirane datoteke iz UAT-I-01 do UAT-I-03.",
          "Postaviti pitanje 'Pokušava li netko provaliti?' u obliku u kojem ga šalje sučelje (engleski upit), top 5.",
          "HTTP 200; izvještaj s razinom rizika, sažetkom, pokazateljima i preporukama; pet dokaza; istaknuti dokazi postoje među dohvaćenima.")
def t_pitanje():
    s, js, ms = zahtjev("GET", "/logs/query/rag_local_mode", {"q": PITANJE_EN, "top_k": 5, "mode": "auto"})
    rep, ev, hl, izm, polja = _provjeri_izvjestaj(js)
    KONTEKST["pitanje_p02"] = PITANJE_EN
    stvarno = (f"HTTP {s} za {ms / 1000:.1f} s; model {js.get('model')}; rizik {rep.get('risk_level')}; dokaza {len(ev)}; "
               f"istaknutih {len(hl)}, od toga nepostojećih {len(izm)}")
    return stvarno, s == 200 and polja and len(ev) == 5 and not izm, ""


@scenarij("UAT-P-03", C4, "rubni", "Pitanje na hrvatskom izvan predloška",
          "Kao UAT-P-02.", "Postaviti izravno pitanje 'Pokušava li netko provaliti?' bez preslikavanja na engleski.",
          "HTTP 200; izvještaj u zadanom obliku s dohvaćenim dokazima.")
def t_hr():
    s, js, ms = zahtjev("GET", "/logs/query/rag_local_mode", {"q": PITANJE_HR, "top_k": 5, "mode": "auto"})
    rep, ev, hl, izm, polja = _provjeri_izvjestaj(js)
    return (f"HTTP {s} za {ms / 1000:.1f} s; rizik {rep.get('risk_level')}; dokaza {len(ev)}; nepostojećih istaknutih {len(izm)}",
            s == 200 and polja and len(ev) == 5 and not izm,
            "Kvaliteta dohvata za hrvatski upit ovdje se ne ocjenjuje, provjerava se samo ispravnost rada.")


@scenarij("UAT-P-04", C4, "rubni", "Veći broj dokaza (top 10)",
          "Kao UAT-P-02.", "Postaviti isto pitanje uz deset dokaza.",
          "HTTP 200; dohvaćeno deset dokaza; izvještaj u zadanom obliku.")
def t_top10():
    s, js, ms = zahtjev("GET", "/logs/query/rag_local_mode", {"q": PITANJE_EN, "top_k": 10, "mode": "auto"})
    rep, ev, hl, izm, polja = _provjeri_izvjestaj(js)
    return (f"HTTP {s} za {ms / 1000:.1f} s; dokaza {len(ev)}; nepostojećih istaknutih {len(izm)}",
            s == 200 and polja and len(ev) == 10 and not izm, "")


@scenarij("UAT-P-05", C4, "neuspješan", "Prazno pitanje",
          "Poslužitelj radi.", "Poslati prazno pitanje izravno sučelju za programiranje (sučelje u pregledniku gumb tada onemogućuje).",
          "Zahtjev se odbija (HTTP 4xx) ili sustav jasno javlja da pitanje nedostaje.")
def t_prazno():
    s, js, ms = zahtjev("GET", "/logs/query/rag_local_mode", {"q": "", "top_k": 5, "mode": "auto"})
    rep = js.get("report", {})
    stvarno = f"HTTP {s} za {ms / 1000:.1f} s; " + (f"izvještaj s rizikom {rep.get('risk_level')}" if s == 200 else str(js.get("detail"))[:120])
    return stvarno, 400 <= s < 500, "Ako poslužitelj prihvati prazno pitanje, zaštitu pruža samo onemogućeni gumb u sučelju."


@scenarij("UAT-P-06", C4, "uspješan", "Usporedba odgovora dvaju modela",
          "Kao UAT-P-02.", "Pozvati /logs/query/compare_models za zadane modele llama3.1:8b i llama3.2:1b.",
          "Za svaki model vraća se izvještaj s razinom rizika i vremenom ili jasna poruka o pogrešci.")
def t_compare_models():
    s, js, ms = zahtjev("GET", "/logs/query/compare_models", {"q": PITANJE_EN, "top_k": 5})
    rr = js.get("results", [])
    opis = "; ".join(f"{r.get('model')}: " + (f"rizik {r.get('risk_level')}, {r.get('inference_ms')} ms"
                                               if not r.get("error") else f"pogreška {str(r.get('error'))[:60]}") for r in rr)
    return f"HTTP {s} za {ms / 1000:.1f} s; {opis}", s == 200 and len(rr) == 2 and all(r.get("risk_level") or r.get("error") for r in rr), ""


@scenarij("UAT-H-01", C5, "uspješan", "Povijest postavljenih pitanja",
          "UAT-P-02 do UAT-P-04 izvedeni.", "Pozvati /logs/history.",
          "Povijest sadrži postavljena pitanja s vremenom, brojem dokaza i izvještajem.")
def t_povijest():
    s, js, ms = zahtjev("GET", "/logs/history", {"limit": 50})
    h = js.get("history", [])
    nadjeno = [x for x in h if x.get("query") == KONTEKST.get("pitanje_p02")]
    return f"HTTP {s}; zapisa u povijesti {len(h)}; zapisa za pitanje iz UAT-P-02: {len(nadjeno)}", \
        s == 200 and len(nadjeno) >= 1, ""


@scenarij("UAT-H-02", C5, "rubni", "Ograničenje broja zapisa povijesti",
          "UAT-H-01 prošao.", "Pozvati /logs/history s ograničenjem 1.",
          "Vraća se točno jedan, najnoviji zapis.")
def t_povijest_1():
    s, js, _ = zahtjev("GET", "/logs/history", {"limit": 1})
    h = js.get("history", [])
    _, sve, _ = zahtjev("GET", "/logs/history", {"limit": 50})
    najnoviji = max((x.get("queried_at", "") for x in sve.get("history", [])), default=None)
    return f"HTTP {s}; zapisa {len(h)}; vrijeme zapisa {h[0].get('queried_at') if h else None}, najnovije {najnoviji}", \
        s == 200 and len(h) == 1 and h[0].get("queried_at") == najnoviji, ""


REDOSLIJED = [t_prazan_indeks, t_upload_cicids, t_normalize, t_vlastiti, t_inf_nan, t_txt, t_neispravan, t_prazan,
              t_index_veliki, t_index_mali, t_index_bez_meta, t_semanticka, t_compare, t_filter, t_index_404,
              t_modeli, t_klasifikacija, t_bez_obiljezja, t_krivi_model, t_klas_404, t_compare_rag,
              t_pitanje, t_hr, t_top10, t_prazno, t_compare_models, t_povijest, t_povijest_1]


# ─────────────────────────────────────────────────────────────────────────────
def pronadji_cicids() -> Path | None:
    kandidati = [p for p in (PROJEKT / "data" / "uploads").glob("*.csv") if "ISCX" in p.name]
    kandidati += list(PROJEKT.glob("**/MachineLearningCVE/*.csv"))
    kandidati = [p for p in kandidati if "uat_" not in p.name]
    if not kandidati:
        return None
    # najmanja datoteka koja ipak ima više od 5000 zapisa (sve datoteke CICIDS2017 imaju)
    return min(kandidati, key=lambda p: p.stat().st_size)


def zapisi_md(meta, izlaz: Path):
    L = [f"# Test korisničkog prihvaćanja — NetlogRAG\n",
         f"- Tester: {meta['tester']}", f"- Izvedeno: {meta['pocetak']} – {meta['kraj']}",
         f"- Okruženje: {meta['os']}, Python {meta['python']}", f"- Ispitna datoteka: {meta['cicids']}",
         f"- Ukupno: {meta['ukupno']}, prošlo: {meta['proslo']}, nije prošlo: {meta['nije_proslo']}\n"]
    for c in (C1, C2, C3, C4, C5):
        L.append(f"## {c}\n")
        L.append("| ID | Vrsta | Scenarij | Preduvjeti | Koraci | Očekivani rezultat | Stvarni rezultat | Status | Napomena |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for r in [x for x in REZULTATI if x["cjelina"] == c]:
            cell = lambda v: str(v).replace("|", "/").replace("\n", " ")  # noqa: E731
            L.append("| " + " | ".join(cell(r[k]) for k in ("id", "vrsta", "scenarij", "preduvjeti", "koraci",
                                                              "ocekivano", "stvarno", "status", "napomena")) + " |")
        L.append("")
    izlaz.write_text("\n".join(L), encoding="utf-8")


def main():
    global BASE
    ap = argparse.ArgumentParser()
    ap.add_argument("--tester", default="T1 (autor)")
    ap.add_argument("--cicids", type=Path, default=None)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--zadrzi-okruzenje", action="store_true")
    a = ap.parse_args()

    cic = a.cicids or pronadji_cicids()
    if not cic or not cic.exists():
        sys.exit("Nije pronađena datoteka skupa CICIDS2017; zadajte je s --cicids <putanja>.")
    KONTEKST["cicids"] = cic

    oznaka = datetime.now().strftime("%Y%m%d_%H%M%S")
    okr = PROJEKT / "uat_okruzenje" / oznaka
    (okr / "data").mkdir(parents=True, exist_ok=True)
    KONTEKST["podaci"] = pripremi_podatke(cic, okr / "ulaz")

    env = dict(os.environ)
    env["CHROMA_DIR"] = str(okr / "data" / "chroma")
    env["UPLOAD_DIR"] = str(okr / "data" / "uploads")
    env["PYTHONIOENCODING"] = "utf-8"
    log = open(okr / "posluzitelj.log", "w", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--app-dir", str(PROJEKT),
                             "--port", str(a.port)], cwd=okr, env=env, stdout=log, stderr=subprocess.STDOUT)
    BASE = f"http://127.0.0.1:{a.port}"
    print(f"Ispitno okruženje: {okr}\nPokrećem poslužitelj na {BASE} ...", flush=True)
    for _ in range(240):
        try:
            if zahtjev("GET", "/health", timeout=2)[0] == 200:
                break
        except Exception:
            time.sleep(1)
    else:
        proc.terminate()
        sys.exit(f"Poslužitelj se nije pokrenuo; vidi {okr / 'posluzitelj.log'}")

    pocetak = datetime.now()
    print(f"Datoteka za ispitivanje: {cic}\n")
    try:
        for t in REDOSLIJED:
            t()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except Exception:
            proc.kill()
        log.close()
    kraj = datetime.now()

    meta = {
        "tester": a.tester, "pocetak": pocetak.isoformat(timespec="seconds"), "kraj": kraj.isoformat(timespec="seconds"),
        "os": f"{platform.system()} {platform.release()}", "python": platform.python_version(),
        "cicids": cic.name, "ukupno": len(REZULTATI),
        "proslo": sum(r["status"] == "Prošao" for r in REZULTATI),
        "nije_proslo": sum(r["status"] != "Prošao" for r in REZULTATI),
    }
    out = PROJEKT / "rezultati"
    out.mkdir(exist_ok=True)
    (out / "uat_rezultati.json").write_text(json.dumps({"meta": meta, "scenariji": REZULTATI}, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    zapisi_md(meta, out / "uat_rezultati.md")
    print(f"\nUkupno {meta['ukupno']}, prošlo {meta['proslo']}, nije prošlo {meta['nije_proslo']}.")
    print(f"Rezultati: {out / 'uat_rezultati.json'} i {out / 'uat_rezultati.md'}")
    if not a.zadrzi_okruzenje:
        shutil.rmtree(okr / "data", ignore_errors=True)


if __name__ == "__main__":
    main()