<template>
  <div class="eval-view">

    <div class="page-header">
      <h1>Evaluacija</h1>
      <p class="subtitle">
        Sistemska evaluacija baseline modela na svim CICIDS2017 datasetima.
        Rezultati se koriste u evaluacijskom poglavlju diplomskog rada.
      </p>
    </div>

    <!-- Controls -->
    <div class="controls-card">
      <div class="controls-row">
        <div class="ctrl-group">
          <label class="ctrl-label">Odaberi datasete za evaluaciju</label>
          <div class="file-chips">
            <div
              v-for="f in files" :key="f.filename"
              class="file-chip"
              :class="{ selected: selectedFiles.includes(f.filename) }"
              @click="toggleFile(f.filename)"
            >
              <span class="chip-check">{{ selectedFiles.includes(f.filename) ? '✓' : '+' }}</span>
              {{ shortName(f.filename) }}
            </div>
          </div>
        </div>
        <div class="ctrl-right">
          <select v-model="sampleSize" class="size-select">
            <option :value="5000">5 000 redova</option>
            <option :value="10000">10 000 redova</option>
            <option :value="20000">20 000 redova</option>
          </select>
          <button
            class="btn-eval"
            :disabled="!modelsReady || selectedFiles.length === 0 || loading"
            @click="runEval"
          >
            <span v-if="loading" class="spinner"></span>
            {{ loading ? `Evaluiram (${doneCount}/${selectedFiles.length})...` : 'Pokreni evaluaciju' }}
          </button>
        </div>
      </div>
      <div v-if="!modelsReady" class="warn-bar">
        ⚠ Baseline modeli nisu trenirani. Idi na stranicu <strong>Baseline</strong> i treniraj modele.
      </div>
    </div>

    <div v-if="error" class="error-bar">⚠ {{ error }}</div>

    <!-- Results per dataset -->
    <div v-if="results.length" class="results-section">

      <!-- Overview table -->
      <div class="overview-card">
        <div class="card-title">📊 Pregled rezultata po datasetu</div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Uzoraka</th>
                <th>Klase</th>
                <th colspan="2">Random Forest</th>
                <th colspan="2">XGBoost</th>
              </tr>
              <tr class="sub-header">
                <th></th><th></th><th></th>
                <th>Accuracy</th><th>F1</th>
                <th>Accuracy</th><th>F1</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="r in results" :key="r.file"
                :class="{ 'row-selected': expandedFile === r.file }"
                @click="expandedFile = expandedFile === r.file ? null : r.file"
                style="cursor:pointer"
              >
                <td class="file-cell">
                  <span class="expand-icon">{{ expandedFile === r.file ? '▾' : '▸' }}</span>
                  {{ shortName(r.file) }}
                </td>
                <td>{{ r.n_samples?.toLocaleString() }}</td>
                <td>
                  <div class="class-pills">
                    <span
                      v-for="cls in Object.keys(r.distribution || {})" :key="cls"
                      class="class-pill"
                      :class="cls === 'BENIGN' ? 'pill-ok' : 'pill-danger'"
                    >{{ cls }}</span>
                  </div>
                </td>
                <td :class="scoreClass(r.results?.random_forest?.accuracy)">
                  {{ pct(r.results?.random_forest?.accuracy) }}
                </td>
                <td :class="scoreClass(r.results?.random_forest?.f1_weighted)">
                  {{ pct(r.results?.random_forest?.f1_weighted) }}
                </td>
                <td :class="scoreClass(r.results?.xgboost?.accuracy)">
                  {{ pct(r.results?.xgboost?.accuracy) }}
                </td>
                <td :class="scoreClass(r.results?.xgboost?.f1_weighted)">
                  {{ pct(r.results?.xgboost?.f1_weighted) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Expanded dataset detail -->
      <div v-if="expandedFile" class="detail-card">
        <div class="card-title">
          🔍 Detalji — {{ shortName(expandedFile) }}
        </div>

        <div v-for="r in results.filter(x => x.file === expandedFile)" :key="r.file">

          <!-- Distribution -->
          <div class="detail-section">
            <div class="detail-label">Raspodjela klasa u datasetu</div>
            <div class="dist-bars">
              <div v-for="(count, cls) in r.distribution" :key="cls" class="dist-row">
                <span class="dist-label" :class="cls === 'BENIGN' ? 'ok-text' : 'danger-text'">{{ cls }}</span>
                <div class="dist-track">
                  <div
                    class="dist-fill"
                    :class="cls === 'BENIGN' ? 'fill-ok' : 'fill-danger'"
                    :style="{ width: distPct(count, r.n_samples) + '%' }"
                  ></div>
                </div>
                <span class="dist-count">{{ count.toLocaleString() }} ({{ distPct(count, r.n_samples) }}%)</span>
              </div>
            </div>
          </div>

          <!-- Per-class metrics -->
          <div class="detail-section">
            <div class="detail-label">Metrike po klasi napada</div>
            <div class="per-class-grid">
              <div v-for="(model, mkey) in r.results" :key="mkey" class="per-class-col">
                <div class="per-class-title">{{ mkey === 'random_forest' ? 'Random Forest' : 'XGBoost' }}</div>
                <table class="per-class-table">
                  <thead>
                    <tr><th>Klasa</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="(metrics, cls) in model.per_class" :key="cls">
                      <td :class="cls === 'BENIGN' ? 'ok-text' : 'danger-text'">{{ cls }}</td>
                      <td :class="scoreClass(metrics.precision)">{{ pct(metrics.precision) }}</td>
                      <td :class="scoreClass(metrics.recall)">{{ pct(metrics.recall) }}</td>
                      <td :class="scoreClass(metrics.f1)">{{ pct(metrics.f1) }}</td>
                      <td class="muted-text">{{ metrics.support?.toLocaleString() }}</td>
                    </tr>
                  </tbody>
                </table>
                <div class="inf-speed">
                  Inference: <b>{{ model.inference_ms_per_sample }} ms/zapis</b>
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- Export CSV -->
      <div class="export-row">
        <button class="btn-export" @click="exportCsv">↓ Izvezi rezultate kao CSV</button>
        <span class="export-note">Za korištenje u pisanom dijelu diplomskog rada</span>
      </div>

    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const files        = ref([])
const selectedFiles= ref([])
const sampleSize   = ref(10000)
const modelsReady  = ref(false)
const loading      = ref(false)
const error        = ref(null)
const results      = ref([])
const doneCount    = ref(0)
const expandedFile = ref(null)

async function loadData() {
  try {
    const [filesRes, statusRes] = await Promise.all([
      axios.get('/logs/files'),
      axios.get('/logs/baseline/status'),
    ])
    files.value       = filesRes.data.files ?? []
    modelsReady.value = statusRes.data.trained
  } catch (e) { console.error(e) }
}

function toggleFile(filename) {
  const idx = selectedFiles.value.indexOf(filename)
  if (idx === -1) selectedFiles.value.push(filename)
  else selectedFiles.value.splice(idx, 1)
}

async function runEval() {
  loading.value  = true
  error.value    = null
  results.value  = []
  doneCount.value = 0

  for (const filename of selectedFiles.value) {
    try {
      const { data } = await axios.get('/logs/baseline/evaluate', {
        params: { filename, sample_size: sampleSize.value }
      })
      if (data.error) {
        results.value.push({ file: filename, error: data.error })
      } else {
        results.value.push(data)
      }
    } catch (e) {
      results.value.push({ file: filename, error: e.response?.data?.detail ?? 'Greška' })
    }
    doneCount.value++
  }
  loading.value = false
}

function shortName(filename) {
  return filename
    .replace(/^\d+_/, '')
    .replace('_Tuesday-WorkingHours.pcap_ISCX.csv', ' (Tue)')
    .replace('_Wednesday-workingHours.pcap_ISCX.csv', ' (Wed)')
    .replace('_Thursday-WorkingHours-Morning-WebAttacks.pcap_ISCX.csv', ' (Thu-Web)')
    .replace('_Thursday-WorkingHours-Afternoon-Infilteration.pcap_ISCX.csv', ' (Thu-Inf)')
    .replace('_Friday-WorkingHours-Afternoon-DDos.pcap_ISCX.csv', ' (Fri-DDoS)')
    .replace('_Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv', ' (Fri-Scan)')
    .replace('_Friday-WorkingHours-Morning.pcap_ISCX.csv', ' (Fri-Bot)')
    .replace('_Monday-WorkingHours.pcap_ISCX.csv', ' (Mon)')
    .replace('.csv', '')
    .replace('sample_logs', 'Sample logs')
}

function pct(val) {
  return val != null ? (val * 100).toFixed(1) + '%' : '—'
}

function scoreClass(val) {
  if (val == null) return ''
  if (val >= 0.95) return 'score-high'
  if (val >= 0.80) return 'score-mid'
  return 'score-low'
}

function distPct(count, total) {
  return total ? Math.round((count / total) * 100) : 0
}

function exportCsv() {
  const rows = [['Dataset', 'Uzoraka', 'RF Accuracy', 'RF F1', 'XGB Accuracy', 'XGB F1', 'RF Inference ms', 'XGB Inference ms']]
  for (const r of results.value) {
    rows.push([
      shortName(r.file),
      r.n_samples ?? '',
      r.results?.random_forest?.accuracy ?? '',
      r.results?.random_forest?.f1_weighted ?? '',
      r.results?.xgboost?.accuracy ?? '',
      r.results?.xgboost?.f1_weighted ?? '',
      r.results?.random_forest?.inference_ms_per_sample ?? '',
      r.results?.xgboost?.inference_ms_per_sample ?? '',
    ])
  }
  const csv  = rows.map(r => r.join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = 'evaluacija_rezultati.csv'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(loadData)
</script>

<style scoped>
.eval-view { display: flex; flex-direction: column; gap: 1.5rem; }

.page-header h1 {
  font-family: var(--font-head); font-size: 1.8rem;
  font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }

/* Controls */
.controls-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.2rem 1.4rem;
  display: flex; flex-direction: column; gap: 1rem;
}
.controls-row { display: flex; gap: 1.5rem; flex-wrap: wrap; align-items: flex-start; }
.ctrl-group   { flex: 1; min-width: 300px; display: flex; flex-direction: column; gap: 0.6rem; }
.ctrl-label   { font-size: 0.75rem; color: var(--muted); letter-spacing: 0.06em; font-weight: 600; }
.ctrl-right   { display: flex; flex-direction: column; gap: 0.6rem; align-items: flex-end; justify-content: flex-end; }

.file-chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.file-chip {
  display: flex; align-items: center; gap: 0.4rem;
  background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: 8px; padding: 0.35rem 0.8rem;
  font-size: 0.78rem; cursor: pointer; transition: all 0.15s;
}
.file-chip:hover   { border-color: var(--accent); }
.file-chip.selected{ border-color: var(--accent); background: var(--accent-dim); color: var(--accent); }
.chip-check { font-size: 0.7rem; font-weight: 700; }

.size-select {
  background: var(--bg-hover); border: 1px solid var(--border);
  color: var(--muted); border-radius: 7px; padding: 0.4rem 0.6rem;
  font-size: 0.8rem; outline: none; cursor: pointer;
}
.btn-eval {
  display: flex; align-items: center; gap: 0.5rem;
  background: var(--accent); color: #000; border: none; border-radius: 7px;
  padding: 0.5rem 1.3rem; font-weight: 700; font-size: 0.82rem;
  cursor: pointer; transition: all 0.2s; white-space: nowrap;
}
.btn-eval:hover:not(:disabled) { filter: brightness(1.15); }
.btn-eval:disabled { opacity: 0.4; cursor: not-allowed; }
.spinner {
  width: 11px; height: 11px; border: 2px solid #00000044;
  border-top-color: #000; border-radius: 50%;
  animation: spin 0.6s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

.warn-bar {
  background: #ffb34715; border: 1px solid #ffb34744;
  color: var(--warn); border-radius: 8px; padding: 0.6rem 1rem; font-size: 0.82rem;
}
.error-bar {
  background: #ff4d4d15; border: 1px solid #ff4d4d44;
  color: var(--danger); border-radius: 8px; padding: 0.7rem 1rem; font-size: 0.85rem;
}

/* Results */
.results-section { display: flex; flex-direction: column; gap: 1rem; }
.overview-card, .detail-card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
}
.card-title {
  padding: 0.8rem 1.2rem; border-bottom: 1px solid var(--border);
  font-size: 0.85rem; font-weight: 600;
}

.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
th {
  text-align: left; padding: 0.5rem 0.8rem;
  border-bottom: 1px solid var(--border); color: var(--muted);
  background: var(--bg-hover); font-size: 0.73rem; letter-spacing: 0.04em; white-space: nowrap;
}
.sub-header th { background: var(--bg-card); font-size: 0.7rem; color: var(--muted); }
td { padding: 0.45rem 0.8rem; border-bottom: 1px solid var(--border); white-space: nowrap; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg-hover); }
.row-selected td { background: var(--accent-dim) !important; }

.file-cell { display: flex; align-items: center; gap: 0.4rem; font-size: 0.78rem; }
.expand-icon { color: var(--accent); font-size: 0.7rem; }

.class-pills { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.class-pill  { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.68rem; font-weight: 600; }
.pill-ok     { background: #39d98a22; color: var(--ok);     border: 1px solid #39d98a44; }
.pill-danger { background: #ff4d4d18; color: var(--danger); border: 1px solid #ff4d4d44; }

.score-high { color: var(--ok);     font-weight: 700; }
.score-mid  { color: var(--warn);   font-weight: 600; }
.score-low  { color: var(--danger); font-weight: 600; }

/* Detail */
.detail-section { padding: 1rem 1.2rem; border-bottom: 1px solid var(--border); }
.detail-section:last-child { border-bottom: none; }
.detail-label { font-size: 0.72rem; color: var(--muted); font-weight: 600; letter-spacing: 0.06em; margin-bottom: 0.7rem; }

.dist-bars  { display: flex; flex-direction: column; gap: 0.5rem; }
.dist-row   { display: flex; align-items: center; gap: 0.7rem; }
.dist-label { font-size: 0.75rem; font-weight: 600; width: 160px; flex-shrink: 0; }
.dist-track { flex: 1; height: 8px; background: var(--bg-hover); border-radius: 4px; overflow: hidden; }
.dist-fill  { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
.fill-ok     { background: var(--ok); }
.fill-danger { background: var(--danger); }
.dist-count { font-size: 0.72rem; color: var(--muted); white-space: nowrap; }

.ok-text     { color: var(--ok); }
.danger-text { color: var(--danger); }
.muted-text  { color: var(--muted); }

.per-class-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 720px) { .per-class-grid { grid-template-columns: 1fr; } }
.per-class-col  { display: flex; flex-direction: column; gap: 0.5rem; }
.per-class-title{ font-size: 0.8rem; font-weight: 700; }
.per-class-table{ width: 100%; border-collapse: collapse; font-size: 0.76rem; }
.per-class-table th { background: var(--bg-hover); padding: 0.35rem 0.6rem; color: var(--muted); font-size: 0.68rem; text-align: left; border-bottom: 1px solid var(--border); }
.per-class-table td { padding: 0.35rem 0.6rem; border-bottom: 1px solid var(--border); }
.per-class-table tr:last-child td { border-bottom: none; }
.inf-speed { font-size: 0.74rem; color: var(--muted); margin-top: 0.3rem; }
.inf-speed b { color: var(--text); }

/* Export */
.export-row { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.btn-export {
  background: var(--bg-card); border: 1px solid var(--border);
  color: var(--text); border-radius: 7px; padding: 0.5rem 1.1rem;
  font-size: 0.82rem; font-weight: 600; cursor: pointer; transition: all 0.2s;
}
.btn-export:hover { border-color: var(--accent); color: var(--accent); }
.export-note { font-size: 0.75rem; color: var(--muted); font-style: italic; }
</style>