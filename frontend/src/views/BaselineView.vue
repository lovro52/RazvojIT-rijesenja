<template>
  <div class="baseline-view">

    <div class="page-header">
      <h1>Baseline modeli</h1>
      <p class="subtitle">
        Usporedba klasičnih ML modela (Random Forest, XGBoost) s LLM RAG pristupom.
        Obavezna evaluacija za diplomski rad.
      </p>
    </div>

    <!-- Status / Train -->
    <div class="train-card">
      <div class="train-status">
        <span class="status-dot" :class="status.trained ? 'dot-ok' : 'dot-warn'"></span>
        <span class="status-text">
          {{ status.trained ? 'Modeli su trenirani' : 'Modeli nisu trenirani' }}
        </span>
        <span v-if="status.meta?.trained_on" class="status-meta">
          — {{ status.meta.trained_on.split(/[\\/]/).pop() }},
          {{ status.meta.sample_size?.toLocaleString() }} zapisa,
          {{ status.meta.classes?.length }} klasa
        </span>
      </div>

      <div class="train-controls">
        <select v-model="trainFile" class="file-select">
          <option value="">Odaberi CSV datoteku...</option>
          <option v-for="f in files" :key="f.filename" :value="f.filename">
            {{ f.filename }}
          </option>
        </select>
        <select v-model="sampleSize" class="size-select">
          <option :value="5000">5 000 redova</option>
          <option :value="10000">10 000 redova</option>
          <option :value="20000">20 000 redova</option>
          <option :value="50000">50 000 redova</option>
        </select>
        <button class="btn-train" :disabled="!trainFile || training" @click="runTrain">
          <span v-if="training" class="spinner"></span>
          {{ training ? 'Treniram...' : 'Treniraj modele' }}
        </button>
      </div>
      <div v-if="trainNote" class="train-note">⚠ {{ trainNote }}</div>
    </div>

    <div v-if="trainError" class="error-bar">⚠ {{ trainError }}</div>

    <!-- Training results -->
    <div v-if="trainResult" class="metrics-section">
      <div class="section-title">📊 Rezultati treniranja</div>

      <div class="metrics-grid">
        <div v-for="(m, key) in trainResult.results" :key="key" class="metric-card">
          <div class="metric-header">
            <span class="metric-name">{{ m.name }}</span>
            <span class="metric-badge" :class="key === 'xgboost' ? 'badge-xgb' : 'badge-rf'">
              {{ key === 'xgboost' ? 'XGB' : 'RF' }}
            </span>
          </div>

          <div class="metric-rows">
            <div class="metric-row">
              <span class="metric-label">Accuracy</span>
              <div class="metric-bar-wrap">
                <div class="metric-bar">
                  <div class="metric-fill acc-fill" :style="{ width: (m.accuracy * 100) + '%' }"></div>
                </div>
                <span class="metric-val">{{ (m.accuracy * 100).toFixed(1) }}%</span>
              </div>
            </div>
            <div class="metric-row">
              <span class="metric-label">F1 (weighted)</span>
              <div class="metric-bar-wrap">
                <div class="metric-bar">
                  <div class="metric-fill f1-fill" :style="{ width: (m.f1_weighted * 100) + '%' }"></div>
                </div>
                <span class="metric-val">{{ (m.f1_weighted * 100).toFixed(1) }}%</span>
              </div>
            </div>
            <div class="metric-row">
              <span class="metric-label">Precision</span>
              <div class="metric-bar-wrap">
                <div class="metric-bar">
                  <div class="metric-fill pre-fill" :style="{ width: (m.precision * 100) + '%' }"></div>
                </div>
                <span class="metric-val">{{ (m.precision * 100).toFixed(1) }}%</span>
              </div>
            </div>
            <div class="metric-row">
              <span class="metric-label">Recall</span>
              <div class="metric-bar-wrap">
                <div class="metric-bar">
                  <div class="metric-fill rec-fill" :style="{ width: (m.recall * 100) + '%' }"></div>
                </div>
                <span class="metric-val">{{ (m.recall * 100).toFixed(1) }}%</span>
              </div>
            </div>
          </div>

          <div class="metric-speed">
            <span>Treniranje: <b>{{ m.train_time_ms?.toLocaleString() }} ms</b></span>
            <span>Inference: <b>{{ m.inference_ms_per_sample }} ms/zapis</b></span>
          </div>
        </div>
      </div>

      <!-- Classes detected -->
      <div class="classes-card">
        <div class="classes-title">Detektirane klase napada</div>
        <div class="classes-list">
          <span
            v-for="cls in trainResult.classes" :key="cls"
            class="class-chip"
            :class="cls === 'BENIGN' ? 'chip-ok' : 'chip-danger'"
          >{{ cls }}</span>
        </div>
      </div>
    </div>

    <!-- LLM vs ML comparison table -->
    <div v-if="trainResult" class="comparison-section">
      <div class="section-title">⚖️ Usporedba pristupa: ML vs LLM (RAG)</div>
      <div class="comparison-table-wrap">
        <table class="comparison-table">
          <thead>
            <tr>
              <th>Kriterij</th>
              <th class="col-rf">Random Forest</th>
              <th class="col-xgb">XGBoost</th>
              <th class="col-llm">LLM RAG (NetlogRAG)</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Ulazni podaci</td>
              <td>Numerički flow feature-i</td>
              <td>Numerički flow feature-i</td>
              <td>Tekst / prirodni jezik</td>
            </tr>
            <tr>
              <td>Accuracy (CICIDS2017)</td>
              <td class="val-good">{{ trainResult.results.random_forest ? (trainResult.results.random_forest.accuracy * 100).toFixed(1) + '%' : '—' }}</td>
              <td class="val-good">{{ trainResult.results.xgboost ? (trainResult.results.xgboost.accuracy * 100).toFixed(1) + '%' : '—' }}</td>
              <td class="val-muted">Nije primjenjivo*</td>
            </tr>
            <tr>
              <td>F1 Score</td>
              <td class="val-good">{{ trainResult.results.random_forest ? (trainResult.results.random_forest.f1_weighted * 100).toFixed(1) + '%' : '—' }}</td>
              <td class="val-good">{{ trainResult.results.xgboost ? (trainResult.results.xgboost.f1_weighted * 100).toFixed(1) + '%' : '—' }}</td>
              <td class="val-muted">Nije primjenjivo*</td>
            </tr>
            <tr>
              <td>Inference / zapis</td>
              <td class="val-good">{{ trainResult.results.random_forest?.inference_ms_per_sample }} ms</td>
              <td class="val-good">{{ trainResult.results.xgboost?.inference_ms_per_sample }} ms</td>
              <td class="val-warn">1 000 – 10 000 ms</td>
            </tr>
            <tr>
              <td>Objašnjenje odluke</td>
              <td class="val-warn">Ograničeno</td>
              <td class="val-warn">Ograničeno</td>
              <td class="val-good">Detaljno (prirodni jezik)</td>
            </tr>
            <tr>
              <td>Novi formati logova</td>
              <td class="val-warn">Potreban re-train</td>
              <td class="val-warn">Potreban re-train</td>
              <td class="val-good">Bez re-traina</td>
            </tr>
            <tr>
              <td>Razumljivo netehničarima</td>
              <td class="val-danger">Ne</td>
              <td class="val-danger">Ne</td>
              <td class="val-good">Da</td>
            </tr>
            <tr>
              <td>Veličina modela</td>
              <td class="val-good">&lt; 100 MB</td>
              <td class="val-good">&lt; 50 MB</td>
              <td class="val-warn">1 – 8 GB</td>
            </tr>
            <tr>
              <td>Privatnost podataka</td>
              <td class="val-good">✓ Lokalno</td>
              <td class="val-good">✓ Lokalno</td>
              <td class="val-good">✓ Lokalno (Ollama)</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="table-note">* LLM RAG ne daje numeričku klasifikaciju već semantičku analizu — metrike F1/accuracy se ne primjenjuju direktno.</p>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api, { errorMessage } from '../services/api'

const status     = ref({ trained: false })
const files      = ref([])
const trainFile  = ref('')
const sampleSize = ref(20000)
const training   = ref(false)
const trainError = ref(null)
const trainNote  = ref(null)
const trainResult = ref(null)

async function loadStatus() {
  try {
    const { data } = await api.get('/logs/baseline/status')
    status.value = data
  } catch (e) {
    trainError.value = errorMessage(e, 'Nije moguće učitati status modela.')
  }
}

async function loadFiles() {
  try {
    const { data } = await api.get('/logs/files')
    files.value = data.files ?? []
  } catch (e) {
    trainError.value = errorMessage(e, 'Nije moguće učitati datoteke.')
  }
}

async function runTrain() {
  if (!trainFile.value) return
  training.value   = true
  trainError.value = null
  trainNote.value  = sampleSize.value >= 20000
    ? 'Treniranje može trajati 1-3 minute za 20k+ redova...'
    : null

  try {
    const { data } = await api.post('/logs/baseline/train', null, {
      params: { filename: trainFile.value, sample_size: sampleSize.value }
    })
    if (data.error) {
      trainError.value = data.error
    } else {
      trainResult.value = data
      await loadStatus()
    }
  } catch (e) {
    trainError.value = errorMessage(e, 'Treniranje nije uspjelo.')
  } finally {
    training.value  = false
    trainNote.value = null
  }
}

onMounted(() => { loadStatus(); loadFiles() })
</script>

<style scoped>
.baseline-view { display: flex; flex-direction: column; gap: 1.5rem; }

.page-header h1 {
  font-family: var(--font-head); font-size: 1.8rem;
  font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }

/* Train card */
.train-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.2rem 1.4rem;
  display: flex; flex-direction: column; gap: 1rem;
}
.train-status { display: flex; align-items: center; gap: 0.6rem; font-size: 0.85rem; flex-wrap: wrap; }
.status-dot   { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-ok   { background: var(--ok); }
.dot-warn { background: var(--warn); }
.status-text { font-weight: 600; }
.status-meta { color: var(--muted); font-size: 0.78rem; }

.train-controls { display: flex; gap: 0.7rem; flex-wrap: wrap; align-items: center; }
.file-select {
  flex: 1; min-width: 200px; background: var(--bg-hover); border: 1px solid var(--border);
  color: var(--text); border-radius: 7px; padding: 0.45rem 0.7rem;
  font-size: 0.82rem; outline: none; cursor: pointer;
}
.size-select {
  background: var(--bg-hover); border: 1px solid var(--border);
  color: var(--muted); border-radius: 7px; padding: 0.45rem 0.6rem;
  font-size: 0.8rem; outline: none; cursor: pointer;
}
.btn-train {
  display: flex; align-items: center; gap: 0.5rem;
  background: var(--accent); color: #000; border: none; border-radius: 7px;
  padding: 0.5rem 1.3rem; font-weight: 700; font-size: 0.82rem;
  letter-spacing: 0.05em; cursor: pointer; transition: all 0.2s; white-space: nowrap;
}
.btn-train:hover:not(:disabled) { filter: brightness(1.15); }
.btn-train:disabled { opacity: 0.4; cursor: not-allowed; }
.train-note { font-size: 0.78rem; color: var(--warn); }

.spinner {
  width: 11px; height: 11px; border: 2px solid #00000044;
  border-top-color: #000; border-radius: 50%;
  animation: spin 0.6s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

.error-bar {
  background: #ff4d4d15; border: 1px solid #ff4d4d44;
  color: var(--danger); border-radius: 8px; padding: 0.7rem 1rem; font-size: 0.85rem;
}

/* Metrics */
.section-title { font-size: 0.9rem; font-weight: 700; margin-bottom: 0.2rem; }
.metrics-section { display: flex; flex-direction: column; gap: 1rem; }

.metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 680px) { .metrics-grid { grid-template-columns: 1fr; } }

.metric-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.1rem 1.2rem;
  display: flex; flex-direction: column; gap: 0.8rem;
}
.metric-header { display: flex; align-items: center; justify-content: space-between; }
.metric-name   { font-size: 0.95rem; font-weight: 700; }
.metric-badge  { font-size: 0.68rem; font-weight: 800; padding: 0.2rem 0.6rem; border-radius: 5px; }
.badge-rf  { background: #1A73E822; color: var(--accent); border: 1px solid #1A73E844; }
.badge-xgb { background: #16A34A22; color: var(--ok);     border: 1px solid #16A34A44; }

.metric-rows { display: flex; flex-direction: column; gap: 0.5rem; }
.metric-row  { display: flex; align-items: center; gap: 0.6rem; }
.metric-label { font-size: 0.74rem; color: var(--muted); width: 90px; flex-shrink: 0; }
.metric-bar-wrap { display: flex; align-items: center; gap: 0.5rem; flex: 1; }
.metric-bar  { flex: 1; height: 6px; background: var(--bg-hover); border-radius: 3px; overflow: hidden; }
.metric-fill { height: 100%; border-radius: 3px; transition: width 0.6s ease; }
.acc-fill { background: var(--accent); }
.f1-fill  { background: var(--ok); }
.pre-fill { background: var(--warn); }
.rec-fill { background: #a78bfa; }
.metric-val { font-size: 0.75rem; font-weight: 700; width: 40px; text-align: right; }

.metric-speed {
  display: flex; gap: 1rem; font-size: 0.75rem; color: var(--muted);
  border-top: 1px solid var(--border); padding-top: 0.6rem; flex-wrap: wrap;
}
.metric-speed b { color: var(--text); }

/* Classes */
.classes-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1rem 1.2rem;
}
.classes-title { font-size: 0.8rem; font-weight: 600; color: var(--muted); margin-bottom: 0.7rem; }
.classes-list  { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.class-chip {
  padding: 0.2rem 0.7rem; border-radius: 6px; font-size: 0.75rem; font-weight: 600;
}
.chip-ok     { background: #39d98a22; color: var(--ok);     border: 1px solid #39d98a44; }
.chip-danger { background: #ff4d4d18; color: var(--danger); border: 1px solid #ff4d4d44; }

/* Comparison table */
.comparison-section { display: flex; flex-direction: column; gap: 0.8rem; }
.comparison-table-wrap {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; overflow: hidden; overflow-x: auto;
}
.comparison-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
th {
  text-align: left; padding: 0.6rem 0.9rem;
  border-bottom: 1px solid var(--border); font-size: 0.75rem;
  letter-spacing: 0.05em; color: var(--muted); background: var(--bg-hover);
}
.col-rf  { color: var(--accent); }
.col-xgb { color: var(--ok); }
.col-llm { color: var(--warn); }
td { padding: 0.45rem 0.9rem; border-bottom: 1px solid var(--border); }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg-hover); }
td:first-child { color: var(--muted); font-size: 0.75rem; }
.val-good   { color: var(--ok);     font-weight: 600; }
.val-warn   { color: var(--warn);   font-weight: 500; }
.val-danger { color: var(--danger); font-weight: 500; }
.val-muted  { color: var(--muted); }
.table-note { font-size: 0.75rem; color: var(--muted); font-style: italic; }
</style>
