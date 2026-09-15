<template>
  <div class="about-view">

    <div class="page-header">
      <h1>O sustavu</h1>
      <p class="subtitle">Arhitektura, tehnologije i argumentacija dizajnerskih odluka.</p>
    </div>

    <!-- System overview -->
    <div class="hero-card">
      <div class="hero-left">
        <div class="hero-logo">NETLOG<span class="accent">RAG</span></div>
        <div class="hero-desc">
          Sustav za analizu sigurnosnih prijetnji u mrežnim logovima
          temeljen na RAG (Retrieval-Augmented Generation) pristupu
          s lokalnim jezičnim modelom.
        </div>
        <div class="hero-badges">
          <span class="hbadge">Python 3.12</span>
          <span class="hbadge">FastAPI</span>
          <span class="hbadge">Vue 3</span>
          <span class="hbadge">ChromaDB</span>
          <span class="hbadge">Ollama</span>
          <span class="hbadge">LLaMA 3.1</span>
        </div>
      </div>
      <div class="hero-stats">
        <div class="hstat"><span class="hstat-val">RAG</span><span class="hstat-label">Pristup</span></div>
        <div class="hstat"><span class="hstat-val">100%</span><span class="hstat-label">Lokalno</span></div>
        <div class="hstat"><span class="hstat-val">8</span><span class="hstat-label">Stranica</span></div>
        <div class="hstat"><span class="hstat-val">REST</span><span class="hstat-label">API</span></div>
      </div>
    </div>

    <!-- Architecture -->
    <div class="section">
      <div class="section-title">🏗️ Arhitektura sustava</div>
      <div class="arch-grid">
        <div class="arch-card">
          <div class="arch-icon" style="color: var(--accent)">⬡</div>
          <div class="arch-name">Frontend</div>
          <div class="arch-tech">Vue 3 + Vite</div>
          <div class="arch-desc">Single-page aplikacija s 8 pogleda. Tamni dizajn, responzivno sučelje, PDF izvoz.</div>
        </div>
        <div class="arch-card">
          <div class="arch-icon" style="color: var(--ok)">⚡</div>
          <div class="arch-name">Backend API</div>
          <div class="arch-tech">Python + FastAPI</div>
          <div class="arch-desc">REST API s 15+ endpointa za upload, indeksiranje, pretragu i analizu.</div>
        </div>
        <div class="arch-card">
          <div class="arch-icon" style="color: #a78bfa">◈</div>
          <div class="arch-name">Vektorska baza</div>
          <div class="arch-tech">ChromaDB + all-MiniLM-L6-v2</div>
          <div class="arch-desc">Semantičko pretraživanje log zapisa putem vektorskih embeddinga.</div>
        </div>
        <div class="arch-card">
          <div class="arch-icon" style="color: var(--warn)">🧠</div>
          <div class="arch-name">Jezični model</div>
          <div class="arch-tech">Ollama + LLaMA 3.1</div>
          <div class="arch-desc">Lokalno pokretanje LLM modela za generiranje sigurnosnih izvještaja.</div>
        </div>
        <div class="arch-card">
          <div class="arch-icon" style="color: var(--danger)">▣</div>
          <div class="arch-name">Baza podataka</div>
          <div class="arch-tech">SQLite</div>
          <div class="arch-desc">Pohrana log zapisa, metapodataka fajlova i povijesti upita.</div>
        </div>
        <div class="arch-card">
          <div class="arch-icon" style="color: var(--ok)">📊</div>
          <div class="arch-name">Baseline modeli</div>
          <div class="arch-tech">XGBoost + Random Forest</div>
          <div class="arch-desc">Klasični ML modeli za usporedbu s LLM pristupom.</div>
        </div>
      </div>
    </div>

    <!-- RAG flow -->
    <div class="section">
      <div class="section-title">🔄 RAG pipeline — kako sustav radi</div>
      <div class="flow-steps">
        <div class="flow-step">
          <div class="step-num">1</div>
          <div class="step-content">
            <div class="step-title">Upload i normalizacija</div>
            <div class="step-desc">Korisnik uploaduje CSV s mrežnim logovima. Sustav automatski prepoznaje format (CICIDS2017, vlastiti CSV) i normalizira stupce u kanonski format.</div>
          </div>
        </div>
        <div class="flow-arrow">↓</div>
        <div class="flow-step">
          <div class="step-num">2</div>
          <div class="step-content">
            <div class="step-title">Embedding i indeksiranje</div>
            <div class="step-desc">Svaki log zapis se pretvara u numerički vektor (embedding) korištenjem all-MiniLM-L6-v2 modela i pohranjuje u ChromaDB vektorsku bazu.</div>
          </div>
        </div>
        <div class="flow-arrow">↓</div>
        <div class="flow-step">
          <div class="step-num">3</div>
          <div class="step-content">
            <div class="step-title">Semantička pretraga</div>
            <div class="step-desc">Korisnički upit se pretvara u vektor i uspoređuje s vektorima logova. Pronalaze se semantički najrelevantnije zapise — čak i bez točnog podudaranja teksta.</div>
          </div>
        </div>
        <div class="flow-arrow">↓</div>
        <div class="flow-step">
          <div class="step-num">4</div>
          <div class="step-content">
            <div class="step-title">LLM analiza</div>
            <div class="step-desc">Dohvaćeni logovi šalju se lokalnom LLaMA 3.1 modelu koji generira strukturirani sigurnosni izvještaj s razinom rizika, indikatorima i preporukama.</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Why local -->
    <div class="section">
      <div class="section-title">🔒 Zašto lokalno pokretanje modela?</div>
      <div class="privacy-grid">
        <div class="privacy-card critical">
          <div class="privacy-icon">🛡️</div>
          <div class="privacy-title">Privatnost podataka</div>
          <div class="privacy-badge">Kritično</div>
          <div class="privacy-desc">
            Mrežni logovi sadrže IP adrese, portove i obrasce prometa —
            osjetljive poslovne informacije koje ne smiju napustiti organizaciju.
            Lokalni model garantira da podaci ostaju na uređaju.
          </div>
        </div>
        <div class="privacy-card critical">
          <div class="privacy-icon">⚖️</div>
          <div class="privacy-title">GDPR usklađenost</div>
          <div class="privacy-badge">Kritično</div>
          <div class="privacy-desc">
            Slanje log podataka vanjskim cloud API servisima može kršiti
            GDPR regulativu EU. Lokalno pokretanje eliminira taj pravni rizik
            i potrebu za ugovorima o obradi podataka.
          </div>
        </div>
        <div class="privacy-card important">
          <div class="privacy-icon">🔌</div>
          <div class="privacy-title">Air-gapped mreže</div>
          <div class="privacy-badge important-badge">Važno</div>
          <div class="privacy-desc">
            Industrijske, vojne i vladine mreže često nemaju pristup internetu.
            Lokalni model radi i u potpuno izoliranom okruženju bez
            internetske veze.
          </div>
        </div>
        <div class="privacy-card important">
          <div class="privacy-icon">💰</div>
          <div class="privacy-title">Dugoročni troškovi</div>
          <div class="privacy-badge important-badge">Važno</div>
          <div class="privacy-desc">
            Cloud API servisi naplaćuju po upitu — za sustav koji analizira
            tisuće logova dnevno, troškovi rastu eksponencijalno.
            Lokalni model je jednokratna instalacija.
          </div>
        </div>
        <div class="privacy-card important">
          <div class="privacy-icon">⚡</div>
          <div class="privacy-title">Latencija</div>
          <div class="privacy-badge important-badge">Važno</div>
          <div class="privacy-desc">
            Bez mrežnih troškova komunikacije s cloud servisima,
            lokalni model daje brži odgovor — ključno za real-time
            monitoring i detekciju prijetnji.
          </div>
        </div>
        <div class="privacy-card important">
          <div class="privacy-icon">🔧</div>
          <div class="privacy-title">Fine-tuning</div>
          <div class="privacy-badge important-badge">Važno</div>
          <div class="privacy-desc">
            Cloud modeli (OpenAI, Claude, Gemini) ne mogu se
            fine-tunati za specifičnu domenu. Samo lokalni modeli
            se mogu specijalizirati za cybersecurity analizu.
          </div>
        </div>
      </div>
    </div>

    <!-- Detection modes -->
    <div class="section">
      <div class="section-title">🎯 Dva načina detekcije</div>
      <div class="modes-grid">
        <div class="mode-card">
          <div class="mode-header text-mode">
            <span class="mode-icon">📝</span>
            <span class="mode-name">Text / Payload mode</span>
          </div>
          <div class="mode-body">
            <div class="mode-desc">Analiza tekstualnih logova i HTTP payloada. LLM razumije semantiku napada.</div>
            <div class="mode-attacks">
              <span class="attack-chip">SQL Injection</span>
              <span class="attack-chip">XSS</span>
              <span class="attack-chip">Command Injection</span>
              <span class="attack-chip">HTTP anomalije</span>
            </div>
            <div class="mode-advantage">✓ LLM pristup superioran — razumije kontekst</div>
          </div>
        </div>
        <div class="mode-card">
          <div class="mode-header flow-mode">
            <span class="mode-icon">📊</span>
            <span class="mode-name">Network Flow mode</span>
          </div>
          <div class="mode-body">
            <div class="mode-desc">Analiza numeričkih karakteristika mrežnog toka. Klasični ML modeli mogu biti konkurentni.</div>
            <div class="mode-attacks">
              <span class="attack-chip">DDoS</span>
              <span class="attack-chip">Port Scan</span>
              <span class="attack-chip">Brute Force</span>
              <span class="attack-chip">Botnet</span>
            </div>
            <div class="mode-advantage">⚖️ Klasični ML vs LLM — usporedba u evaluaciji</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Datasets -->
    <div class="section">
      <div class="section-title">📁 Korišteni dataseti</div>
      <div class="datasets-list">
        <div class="dataset-row">
          <div class="ds-info">
            <span class="ds-name">CICIDS2017</span>
            <span class="ds-source">University of New Brunswick</span>
          </div>
          <div class="ds-attacks">
            <span class="attack-chip">Brute Force</span>
            <span class="attack-chip">DoS/DDoS</span>
            <span class="attack-chip">Web Attacks</span>
            <span class="attack-chip">Port Scan</span>
            <span class="attack-chip">Botnet</span>
          </div>
          <span class="ds-size">~2.8M zapisa</span>
        </div>
        <div class="dataset-row">
          <div class="ds-info">
            <span class="ds-name">CSE-CIC-IDS2018</span>
            <span class="ds-source">CSE + University of New Brunswick</span>
          </div>
          <div class="ds-attacks">
            <span class="attack-chip">Botnet</span>
            <span class="attack-chip">Infiltration</span>
            <span class="attack-chip">DoS</span>
            <span class="attack-chip">DDoS</span>
          </div>
          <span class="ds-size">~16M zapisa</span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
// Static page — no data fetching needed
</script>

<style scoped>
.about-view { display: flex; flex-direction: column; gap: 2rem; }

.page-header h1 {
  font-family: var(--font-head); font-size: 1.8rem;
  font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }

/* Hero */
.hero-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 16px; padding: 1.8rem 2rem;
  display: flex; align-items: center; gap: 2rem; flex-wrap: wrap;
}
.hero-logo {
  font-family: var(--font-head); font-size: 2rem; font-weight: 800;
  letter-spacing: 0.08em; margin-bottom: 0.6rem;
}
.accent { color: var(--accent); }
.hero-desc { font-size: 0.88rem; color: var(--muted); line-height: 1.7; max-width: 480px; margin-bottom: 0.8rem; }
.hero-badges { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.hbadge {
  background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: 6px; padding: 0.2rem 0.6rem; font-size: 0.72rem; color: var(--text);
}
.hero-stats { display: flex; gap: 1.5rem; margin-left: auto; flex-wrap: wrap; }
.hstat { display: flex; flex-direction: column; align-items: center; gap: 0.2rem; }
.hstat-val { font-family: var(--font-head); font-size: 1.6rem; font-weight: 800; color: var(--accent); }
.hstat-label { font-size: 0.7rem; color: var(--muted); letter-spacing: 0.06em; }

/* Section */
.section { display: flex; flex-direction: column; gap: 1rem; }
.section-title { font-size: 0.95rem; font-weight: 700; }

/* Architecture */
.arch-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0.8rem; }
.arch-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.1rem 1.2rem;
  display: flex; flex-direction: column; gap: 0.4rem;
}
.arch-icon { font-size: 1.4rem; }
.arch-name { font-size: 0.9rem; font-weight: 700; }
.arch-tech { font-size: 0.72rem; color: var(--accent); font-style: italic; }
.arch-desc { font-size: 0.78rem; color: var(--muted); line-height: 1.5; margin-top: 0.2rem; }

/* Flow steps */
.flow-steps { display: flex; flex-direction: column; gap: 0; }
.flow-step {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 10px; padding: 1rem 1.2rem;
  display: flex; align-items: flex-start; gap: 1rem;
}
.flow-arrow { text-align: center; color: var(--border); font-size: 1.2rem; margin: -2px 0; padding-left: 1.5rem; }
.step-num {
  width: 28px; height: 28px; border-radius: 50%;
  background: var(--accent); color: #000;
  display: flex; align-items: center; justify-content: center;
  font-weight: 800; font-size: 0.85rem; flex-shrink: 0;
}
.step-title { font-size: 0.88rem; font-weight: 700; margin-bottom: 0.3rem; }
.step-desc  { font-size: 0.8rem; color: var(--muted); line-height: 1.6; }

/* Privacy */
.privacy-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 0.8rem; }
.privacy-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.1rem 1.2rem;
  display: flex; flex-direction: column; gap: 0.5rem;
}
.privacy-card.critical { border-color: #ff4d4d44; }
.privacy-icon  { font-size: 1.4rem; }
.privacy-title { font-size: 0.9rem; font-weight: 700; }
.privacy-badge {
  display: inline-block; padding: 0.15rem 0.6rem; border-radius: 6px;
  font-size: 0.68rem; font-weight: 700; width: fit-content;
  background: #ff4d4d18; color: var(--danger); border: 1px solid #ff4d4d44;
}
.important-badge {
  background: #ffb34718; color: var(--warn); border: 1px solid #ffb34744;
}
.privacy-desc { font-size: 0.78rem; color: var(--muted); line-height: 1.6; }

/* Modes */
.modes-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 680px) { .modes-grid { grid-template-columns: 1fr; } }
.mode-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
.mode-header {
  display: flex; align-items: center; gap: 0.7rem;
  padding: 0.8rem 1.1rem; font-weight: 700; font-size: 0.9rem;
}
.text-mode { background: #1A73E818; border-bottom: 1px solid #1A73E844; color: var(--accent); }
.flow-mode  { background: #16A34A18; border-bottom: 1px solid #16A34A44; color: var(--ok); }
.mode-icon { font-size: 1.1rem; }
.mode-body { padding: 1rem 1.1rem; display: flex; flex-direction: column; gap: 0.7rem; }
.mode-desc { font-size: 0.82rem; color: var(--muted); line-height: 1.5; }
.mode-attacks { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.attack-chip {
  background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: 6px; padding: 0.15rem 0.55rem; font-size: 0.72rem;
}
.mode-advantage { font-size: 0.78rem; color: var(--muted); font-style: italic; }

/* Datasets */
.datasets-list { display: flex; flex-direction: column; gap: 0.6rem; }
.dataset-row {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.9rem 1.2rem;
  display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap;
}
.ds-info   { display: flex; flex-direction: column; gap: 0.2rem; min-width: 200px; }
.ds-name   { font-size: 0.9rem; font-weight: 700; }
.ds-source { font-size: 0.72rem; color: var(--muted); }
.ds-attacks{ display: flex; flex-wrap: wrap; gap: 0.3rem; flex: 1; }
.ds-size   { font-size: 0.78rem; color: var(--accent); font-weight: 600; white-space: nowrap; margin-left: auto; }
</style>