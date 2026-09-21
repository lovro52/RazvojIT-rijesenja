# Test korisničkog prihvaćanja — NetlogRAG

- Tester: T1 (autor)
- Izvedeno: 2026-09-21T15:15:39 – 2026-09-21T15:16:53
- Okruženje: Windows 10, Python 3.11.7
- Ispitna datoteka: 20260819_160042_Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv
- Ukupno: 28, prošlo: 26, nije prošlo: 2

## Učitavanje i normalizacija

| ID | Vrsta | Scenarij | Preduvjeti | Koraci | Očekivani rezultat | Stvarni rezultat | Status | Napomena |
|---|---|---|---|---|---|---|---|---|
| UAT-U-01 | uspješan | Učitavanje datoteke skupa CICIDS2017 | Poslužitelj radi; datoteka skupa CICIDS2017 dostupna lokalno. | Učitati datoteku kroz /logs/upload. | HTTP 200; datoteka spremljena pod nazivom s vremenskom oznakom; prijavljeni broj redaka i stupaca odgovara datoteci. | HTTP 200 za 652 ms; naziv 20260921_131549_20260819_160042_Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv; redaka 170366; stupaca 79 | Prošao | Očekivani broj redaka: 170366. |
| UAT-U-02 | uspješan | Normalizacija zapisa bez curenja oznake | UAT-U-01 prošao. | Pozvati /logs/normalize za učitanu datoteku i pregledati uzorak zapisa. | Najviše 5000 zapisa; oznaka klase (Label) nije u tekstualnom opisu zapisa nego u zasebnom polju. | HTTP 200 za 870 ms; normaliziranih zapisa 5000; u uzorku od 5 zapisa oznaka u zasebnom polju: 5, oznaka u opisu: 0 | Prošao |  |
| UAT-U-03 | rubni | Vlastiti format zapisa s nazivom protokola | Poslužitelj radi. | Učitati CSV s pet zapisa u kojem je protokol zapisan nazivom (TCP) i normalizirati ga. | HTTP 200; svih pet zapisa normalizirano; protokol prepoznat kao TCP. | učitavanje HTTP 200; normalizacija HTTP 200; zapisa 5; protokoli ['TCP'] | Prošao |  |
| UAT-U-04 | rubni | Beskonačne i nedostajuće vrijednosti obilježja | Poslužitelj radi. | Učitati isječak od 40 zapisa CICIDS2017 u kojem je Flow Bytes/s u prvom zapisu beskonačan, a u drugom prazan; normalizirati. | HTTP 200; zapisi se normaliziraju; beskonačna i nedostajuća vrijednost izostavljene su iz opisa i obilježja toka. | učitavanje HTTP 500; normalizacija HTTP 200; zapisa 40; Flow Bytes/s u 1. zapisu: izostavljeno, u 2. zapisu: izostavljeno; 'inf'/'nan' u opisu: ne | Nije prošao | Učitavanje je vratilo HTTP 500: {'_sirovo': 'Internal Server Error'}. Datoteka je spremljena, a normalizacija je ispravno izostavila vrijednosti. |
| UAT-U-05 | neuspješan | Datoteka koja nije CSV | Poslužitelj radi. | Učitati tekstualnu datoteku s nastavkom .txt. | Zahtjev se odbija (HTTP 400) s porukom da su dopuštene samo datoteke CSV. | HTTP 400: Only .csv files are accepted. | Prošao |  |
| UAT-U-06 | neuspješan | Neispravno oblikovan CSV | Poslužitelj radi. | Učitati CSV u kojem reci imaju više stupaca od zaglavlja. | Zahtjev se odbija (HTTP 400) s porukom da se CSV ne može pročitati; poslužitelj nastavlja raditi. | HTTP 400: Could not parse CSV: Error tokenizing data. C error: Expected 4 fields in line 3, saw 5 ; /health nakon toga: HTTP 200 | Prošao |  |
| UAT-U-07 | rubni | Prazna CSV datoteka | Poslužitelj radi. | Učitati praznu datoteku s nastavkom .csv. | Zahtjev se odbija (HTTP 400) s razumljivom porukom. | HTTP 400: Could not parse CSV: No columns to parse from file | Prošao |  |

## Indeksiranje i pretraživanje

| ID | Vrsta | Scenarij | Preduvjeti | Koraci | Očekivani rezultat | Stvarni rezultat | Status | Napomena |
|---|---|---|---|---|---|---|---|---|
| UAT-I-01 | uspješan | Indeksiranje datoteke iznad granice od 5000 zapisa | UAT-U-01 prošao. | Pozvati /logs/index (bez automatske analize). | HTTP 200; indeksirano točno 5000 zapisa; datoteka označena kao indeksirana. | HTTP 200 za 29.8 s; indeksirano 5000; oznaka indeksiranja u popisu datoteka: True | Prošao |  |
| UAT-I-02 | rubni | Indeksiranje datoteke ispod granice | UAT-U-03 prošao. | Indeksirati datoteku s pet zapisa. | HTTP 200; indeksirano svih pet zapisa. | HTTP 200 za 55 ms; indeksirano 5 | Prošao |  |
| UAT-I-03 | rubni | Zapisi bez adresa, portova i vremenske oznake | UAT-U-04 prošao; datoteka skupa CICIDS2017 ne sadrži izvorišnu adresu ni vremensku oznaku. | Indeksirati isječak od 40 zapisa. | HTTP 200; svi zapisi indeksirani unatoč nedostajućim metapodacima. | HTTP 200 za 278 ms; indeksirano 40 | Prošao |  |
| UAT-I-04 | uspješan | Semantička pretraga | UAT-I-01 prošao. | Pretražiti indeks upitom o pokušajima provale (top 5). | HTTP 200; pet rezultata, svaki s tekstom zapisa, metapodacima i udaljenošću. | HTTP 200 za 9 ms; rezultata 5, potpunih 5 | Prošao |  |
| UAT-I-05 | uspješan | Usporedba pretrage po ključnim riječima i semantičke pretrage | UAT-I-01 prošao. | Pozvati /logs/compare s upitom 'port scan'. | HTTP 200; oba načina vraćaju rezultate i izmjereno vrijeme. | HTTP 200 za 13 ms; ključne riječi: 0 rezultata za 3.99 ms; semantička: 5 rezultata za 6.94 ms | Prošao | Pretraga po ključnim riječima traži doslovno podudaranje, pa može vratiti i nula rezultata. |
| UAT-I-06 | uspješan | Filtriranje zapisa po protokolu | UAT-I-02 prošao. | Pozvati /logs/filter s protokolom TCP. | HTTP 200; vraćeni su samo zapisi s protokolom TCP. | HTTP 200 za 4 ms; zapisa 5, s drugim protokolom 0 | Prošao |  |
| UAT-I-07 | neuspješan | Indeksiranje nepostojeće datoteke | Poslužitelj radi. | Pozvati /logs/index s nazivom koji ne postoji. | HTTP 404 s porukom da datoteka nije pronađena. | HTTP 404: File 'ne_postoji.csv' not found in uploads. | Prošao |  |

## Klasifikacija

| ID | Vrsta | Scenarij | Preduvjeti | Koraci | Očekivani rezultat | Stvarni rezultat | Status | Napomena |
|---|---|---|---|---|---|---|---|---|
| UAT-K-01 | uspješan | Dostupnost prilagođenog modela | Ollama radi. | Pozvati /logs/classifier/models. | Zadani klasifikacijski model naveden je kao instaliran. | HTTP 200; zadani model llama32-netlograg-v3; instalirani ['llama32-netlograg-v3', 'smollm2-netlograg-v3', 'phi35-netlograg-v3'] | Prošao |  |
| UAT-K-02 | uspješan | Klasifikacija deset tokova | UAT-U-01 i UAT-K-01 prošli. | Pozvati /logs/classifier/classify za deset tokova. | Svih deset tokova klasificirano u jednu od sedam klasa i jednu od tri razine rizika, uz izmjereno vrijeme. | HTTP 200 za 4.3 s; klasificirano 10, neuspjelih 0, valjanih oznaka 10; prosjek 309.9 ms po toku; podudarnost s istinitom oznakom 100.0 % na 10 tokova | Prošao | Točnost na deset tokova nije mjera kvalitete modela (vidi poglavlje 8); provjerava se samo ispravnost rada. |
| UAT-K-03 | rubni | Datoteka bez obilježja toka | UAT-U-03 prošao. | Pokušati klasifikaciju datoteke vlastitog formata (bez obilježja CICIDS2017). | HTTP 400 s porukom da datoteka nema obilježja toka potrebna za klasifikaciju. | HTTP 400: Datoteka nema značajke toka potrebne za klasifikaciju (očekuje se CICIDS2017 format). | Prošao |  |
| UAT-K-04 | neuspješan | Nepostojeći klasifikacijski model | UAT-U-01 prošao. | Pokrenuti klasifikaciju pet tokova s modelom koji nije registriran u Ollami. | Zahtjev se odbija s porukom o nedostupnom modelu ili se svi tokovi vraćaju kao neuspješni; nema izmišljenih oznaka. | HTTP 200 za 1241 ms; klasificirano 0, neuspjelih 5 | Prošao | Poslužitelj ne javlja pogrešku nego vraća prazan rezultat; korisnik vidi samo broj neuspjelih tokova. |
| UAT-K-05 | neuspješan | Klasifikacija nepostojeće datoteke | Poslužitelj radi. | Pozvati klasifikaciju s nazivom datoteke koja ne postoji. | HTTP 404 s porukom da datoteka nije pronađena. | HTTP 404: Datoteka nije pronađena | Prošao |  |
| UAT-K-06 | uspješan | Klasifikator i sloj dohvata na istom toku | UAT-I-01 i UAT-K-01 prošli. | Pozvati /logs/classifier/compare_rag za prvi tok datoteke. | Oba sloja vraćaju rezultat; klasifikator vraća tip napada i razinu rizika, sloj dohvata izvještaj s brojem dokaza. | HTTP 200 za 5.0 s; klasifikator: BENIGN/LOW za 170.1 ms; dohvat i generiranje: rizik MEDIUM, dokaza 5, 3568.6 ms; istinita oznaka BENIGN | Prošao |  |

## Postavljanje pitanja i prikaz odgovora

| ID | Vrsta | Scenarij | Preduvjeti | Koraci | Očekivani rezultat | Stvarni rezultat | Status | Napomena |
|---|---|---|---|---|---|---|---|---|
| UAT-P-01 | rubni | Pitanje nad praznim indeksom | Ispitno okruženje tek je pokrenuto; nijedna datoteka nije indeksirana. | Postaviti pitanje (način auto, top 5). | Sustav ne navodi zapise koji ne postoje: izvještaj bez dokaza ili jasna poruka da dokaza nema. | HTTP 200 za 9210 ms; dohvaćeno dokaza: 0; razina rizika: LOW; istaknuti dokazi: nema | Prošao | Bez izmišljenih identifikatora. |
| UAT-P-02 | uspješan | Pitanje iz predloška | Indeksirane datoteke iz UAT-I-01 do UAT-I-03. | Postaviti pitanje 'Pokušava li netko provaliti?' u obliku u kojem ga šalje sučelje (engleski upit), top 5. | HTTP 200; izvještaj s razinom rizika, sažetkom, pokazateljima i preporukama; pet dokaza; istaknuti dokazi postoje među dohvaćenima. | HTTP 200 za 3.2 s; model llama3.1:8b; rizik MEDIUM; dokaza 5; istaknutih 2, od toga nepostojećih 0 | Prošao |  |
| UAT-P-03 | rubni | Pitanje na hrvatskom izvan predloška | Kao UAT-P-02. | Postaviti izravno pitanje 'Pokušava li netko provaliti?' bez preslikavanja na engleski. | HTTP 200; izvještaj u zadanom obliku s dohvaćenim dokazima. | HTTP 200 za 5.0 s; rizik MEDIUM; dokaza 5; nepostojećih istaknutih 0 | Prošao | Kvaliteta dohvata za hrvatski upit ovdje se ne ocjenjuje, provjerava se samo ispravnost rada. |
| UAT-P-04 | rubni | Veći broj dokaza (top 10) | Kao UAT-P-02. | Postaviti isto pitanje uz deset dokaza. | HTTP 200; dohvaćeno deset dokaza; izvještaj u zadanom obliku. | HTTP 200 za 3.4 s; dokaza 10; nepostojećih istaknutih 0 | Prošao |  |
| UAT-P-05 | neuspješan | Prazno pitanje | Poslužitelj radi. | Poslati prazno pitanje izravno sučelju za programiranje (sučelje u pregledniku gumb tada onemogućuje). | Zahtjev se odbija (HTTP 4xx) ili sustav jasno javlja da pitanje nedostaje. | HTTP 200 za 2.7 s; izvještaj s rizikom MEDIUM | Nije prošao | Ako poslužitelj prihvati prazno pitanje, zaštitu pruža samo onemogućeni gumb u sučelju. |
| UAT-P-06 | uspješan | Usporedba odgovora dvaju modela | Kao UAT-P-02. | Pozvati /logs/query/compare_models za zadane modele llama3.1:8b i llama3.2:1b. | Za svaki model vraća se izvještaj s razinom rizika i vremenom ili jasna poruka o pogrešci. | HTTP 200 za 7.8 s; llama3.1:8b: rizik MEDIUM, 7753.1 ms; llama3.2:1b: pogreška model 'llama3.2:1b' not found (status code: 404) | Prošao |  |

## Povijest i izvoz izvještaja

| ID | Vrsta | Scenarij | Preduvjeti | Koraci | Očekivani rezultat | Stvarni rezultat | Status | Napomena |
|---|---|---|---|---|---|---|---|---|
| UAT-H-01 | uspješan | Povijest postavljenih pitanja | UAT-P-02 do UAT-P-04 izvedeni. | Pozvati /logs/history. | Povijest sadrži postavljena pitanja s vremenom, brojem dokaza i izvještajem. | HTTP 200; zapisa u povijesti 5; zapisa za pitanje iz UAT-P-02: 3 | Prošao |  |
| UAT-H-02 | rubni | Ograničenje broja zapisa povijesti | UAT-H-01 prošao. | Pozvati /logs/history s ograničenjem 1. | Vraća se točno jedan, najnoviji zapis. | HTTP 200; zapisa 1; vrijeme zapisa 2026-09-21T13:16:46.023216, najnovije 2026-09-21T13:16:46.023216 | Prošao |  |
