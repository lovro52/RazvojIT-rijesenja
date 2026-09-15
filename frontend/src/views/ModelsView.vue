<template>
  <div class="models-view">

    <div class="page-header">
      <h1>Usporedba modela</h1>
      <p class="subtitle">Pokreni isti upit kroz više modela i usporedi kvalitetu odgovora i brzinu.</p>
    </div>

    <!-- Model selector cards -->
    <div class="model-cards">
      <div
        v-for="m in availableModels"
        :key="m.id"
        class="model-card"
        :class="{ selected: selectedModels.includes(m.id) }"
        @click="toggleModel(m.id)"
      >
        <div class="model-card-top">
          <div class="model-check">{{ selectedModels.includes(m.id) ? '✓' : '' }}</div>
          <span class="model-provider">{{ m.provider }}</span>
        </div>
        <div class="model-name">{{ m.name }}</div>
        <div class="model-size">{{ m.size }}</div>
        <div class="model-desc">{{ m.description }}</div>
      </div>
    </div>

    <div v-if="selectedModels.length < 2" class="select-hint">
      Odaberi najmanje 2 modela za usporedbu
    </div>

    <!-- Search bar -->
    <div class="search-bar" :class="{ disabled: selectedModels.length < 2 }">
      <span class="search-icon">⌕</span>
      <input
        v-model="query"
        type="text"
        placeholder="Upiši sigurnosni upit za usporedbu..."
        :disabled="selectedModels.length < 2"
        @keydown.enter="runCompare"
      />
      <select v-model="topK" class="topk-select">
        <option :value="3">top 3</option>
        <option :value="5">top 5</option>
        <option :value="10">top 10</option>
      </select>
      <button
        class="btn-primary"
        :disabled="!query.trim() || loading || selectedModels.length < 2"
        @click="runCompare"
      >
        <span v-if="loading" class="spinner"></span>
        {{ loading ? `Analiziram (${doneCount}/${selectedModels.length})...` : 'Usporedi modele' }}
      </button>
    </div>

    <!-- Suggested queries -->
    <div v-if="!results.length" class="suggestions">
      <span class="sug-label">Brza pitanja:</span>
      <button v-for="s in suggestions" :key="s" class="sug-pill" @click="query = s">{{ s }}</button>
    </div>

    <div v-if="error" class="error-bar">⚠ {{ error }}</div>

    <!-- Results -->
    <div v-if="results.length" class="results-section">

      <!-- Speed comparison bar -->
      <div class="speed-comparison">
        <div class="speed-title">⚡ Inference brzina</div>
        <div class="speed-bars">
          <div v-for="r in resultsSorted" :key="r.model" class="speed-row">
            <span class="speed-model">{{ modelName(r.model) }}</span>
            <div class="speed-track">
              <div
                class="speed-fill"
                :class="speedFillClass(r.inference_ms)"
                :style="{ width: speedPct(r.inference_ms) + '%' }"
              ></div>
            </div>
            <span class="speed-ms" :class="speedFillClass(r.inference_ms)">
              {{ r.inference_ms ? r.inference_ms + ' ms' : 'greška' }}
            </span>
          </div>
        </div>
      </div>

      <!-- Risk level overview -->
      <div class="risk-overview">
        <div v-for="r in results" :key="r.model" class="risk-chip" :class="riskClass(r.risk_level)">
          <span class="risk-model">{{ modelName(r.model) }}</span>
          <span class="risk-val">{{ r.risk_level ?? 'N/A' }}</span>
        </div>
      </div>

      <!-- Side-by-side results -->
      <div class="compare-grid" :style="{ gridTemplateColumns: `repeat(${results.length}, 1fr)` }">
        <div v-for="r in results" :key="r.model" class="result-col">

          <div class="col-header">
            <span class="col-model">{{ modelName(r.model) }}</span>
            <span class="col-provider">{{ modelProvider(r.model) }}</span>
            <span class="col-ms" :class="speedFillClass(r.inference_ms)">
              {{ r.inference_ms ? r.inference_ms + ' ms' : '' }}
            </span>
          </div>

          <!-- Error state -->
          <div v-if="r.error" class="col-error">
            ⚠ {{ r.error }}
            <div class="col-error-hint">Model možda nije instaliran. Pokreni: <code>ollama pull {{ r.model }}</code></div>
          </div>

          <template v-else>
            <!-- Summary -->
            <div class="result-section">
              <div class="result-label">Sažetak</div>
              <div class="result-text">{{ r.report?.summary ?? '—' }}</div>
            </div>

            <!-- Key indicators -->
            <div class="result-section">
              <div class="result-label warn-label">⚑ Indikatori</div>
              <ul class="result-list">
                <li v-for="(ind, i) in (r.report?.key_indicators ?? [])" :key="i">{{ ind }}</li>
              </ul>
            </div>

            <!-- Recommended actions -->
            <div class="result-section">
              <div class="result-label ok-label">✓ Preporučene akcije</div>
              <ul class="result-list">
                <li v-for="(act, i) in (r.report?.recommended_actions ?? [])" :key="i">{{ act }}</li>
              </ul>
            </div>
          </template>

        </div>
      </div>

      <!-- Summary table -->
      <div class="summary-table-wrap">
        <div class="summary-table-title">📊 Usporedna tablica</div>
        <table class="summary-table">
          <thead>
            <tr>
              <th>Metrika</th>
              <th v-for="r in results" :key="r.model">{{ modelName(r.model) }}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Razina rizika</td>
              <td v-for="r in results" :key="r.model">
                <span class="risk-chip-sm" :class="riskClass(r.risk_level)">{{ r.risk_level ?? '—' }}</span>
              </td>
            </tr>
            <tr>
              <td>Inference (ms)</td>
              <td v-for="r in results" :key="r.model" :class="speedFillClass(r.inference_ms)">
                {{ r.inference_ms ?? '—' }}
              </td>
            </tr>
            <tr>
              <td>Broj indikatora</td>
              <td v-for="r in results" :key="r.model">
                {{ r.report?.key_indicators?.length ?? '—' }}
              </td>
            </tr>
            <tr>
              <td>Broj akcija</td>
              <td v-for="r in results" :key="r.model">
                {{ r.report?.recommended_actions?.length ?? '—' }}
              </td>
            </tr>
            <tr>
              <td>Greška</td>
              <td v-for="r in results" :key="r.model">
                {{ r.error ? 'Da' : 'Ne' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const availableModels = ref([])
const selectedModels  = ref(['llama3.1:8b'])
const query           = ref('')
const topK            = ref(5)
const loading         = ref(false)
const error           = ref(null)
const results         = ref([])
const doneCount       = ref(0)

const suggestions = [
  'Je li mreža sigurna?',
  'Pokušava li netko provaliti?',
  'Ima li skeniranja portova?',
  'Curenje podataka prema vani?',
]

const resultsSorted = computed(() =>
  [...results.value].sort((a, b) => (a.inference_ms ?? 99999) - (b.inference_ms ?? 99999))
)

const maxMs = computed(() =>
  Math.max(...results.value.map(r => r.inference_ms ?? 0), 1)
)

async function loadModels() {
  try {
    const { data } = await axios.get('/logs/models')
    availableModels.value = data.models
  } catch (e) {
    console.error(e)
  }
}

function toggleModel(id) {
  const idx = selectedModels.value.indexOf(id)
  if (idx === -1) {
    selectedModels.value.push(id)
  } else if (selectedModels.value.length > 1) {
    selectedModels.value.splice(idx, 1)
  }
}

async function runCompare() {
  if (!query.value.trim() || selectedModels.value.length < 2) return
  loading.value  = true
  error.value    = null
  results.value  = []
  doneCount.value = 0

  try {
    const { data } = await axios.get('/logs/query/compare_models', {
      params: {
        q:      query.value,
        top_k:  topK.value,
        models: selectedModels.value.join(','),
      }
    })
    results.value   = data.results
    doneCount.value = data.results.length
  } catch (e) {
    error.value = e.response?.data?.detail ?? 'Usporedba nije uspjela.'
  } finally {
    loading.value = false
  }
}

function modelName(id) {
  return availableModels.value.find(m => m.id === id)?.name ?? id
}

function modelProvider(id) {
  return availableModels.value.find(m => m.id === id)?.provider ?? ''
}

function speedPct(ms) {
  return ms ? Math.max(10, Math.round((1 - ms / (maxMs.value * 1.1)) * 100)) : 5
}

function speedFillClass(ms) {
  if (!ms) return 'speed-na'
  if (ms < 3000)  return 'speed-fast'
  if (ms < 8000)  return 'speed-medium'
  return 'speed-slow'
}

function riskClass(level) {
  if (level === 'HIGH')   return 'risk-high'
  if (level === 'MEDIUM') return 'risk-medium'
  if (level === 'LOW')    return 'risk-low'
  return 'risk-na'
}

onMounted(loadModels)
</script>

<style scoped>
.models-view { display: flex; flex-direction: column; gap: 1.4rem; }

.page-header h1 {
  font-family: var(--font-head); font-size: 1.8rem;
  font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }

/* Model selector cards */
.model-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.8rem; }
.model-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1rem 1.1rem; cursor: pointer;
  transition: all 0.18s; display: flex; flex-direction: column; gap: 0.3rem;
}
.model-card:hover   { border-color: var(--accent); }
.model-card.selected { border-color: var(--accent); background: var(--accent-dim); }

.model-card-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.2rem; }
.model-check { width: 18px; height: 18px; border-radius: 50%; border: 1px solid var(--border); font-size: 0.7rem; display: flex; align-items: center; justify-content: center; color: var(--accent); font-weight: 700; }
.model-card.selected .model-check { background: var(--accent); color: #000; border-color: var(--accent); }
.model-provider { font-size: 0.68rem; color: var(--muted); letter-spacing: 0.06em; }
.model-name  { font-size: 0.9rem; font-weight: 700; color: var(--text); }
.model-size  { font-size: 0.72rem; color: var(--accent); }
.model-desc  { font-size: 0.75rem; color: var(--muted); line-height: 1.5; margin-top: 0.2rem; }

.select-hint { font-size: 0.8rem; color: var(--muted); text-align: center; padding: 0.3rem; }

/* Search bar */
.search-bar {
  display: flex; align-items: center; gap: 0.6rem;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.5rem 0.8rem; transition: border-color 0.2s;
}
.search-bar:focus-within:not(.disabled) { border-color: var(--accent); }
.search-bar.disabled { opacity: 0.5; }
.search-icon { color: var(--muted); font-size: 1.1rem; flex-shrink: 0; }
.search-bar input {
  flex: 1; background: none; border: none; outline: none;
  color: var(--text); font-size: 0.9rem; min-width: 0;
}
.search-bar input::placeholder { color: var(--muted); }
.topk-select {
  background: var(--bg-hover); border: 1px solid var(--border);
  color: var(--muted); border-radius: 6px; padding: 0.3rem 0.5rem;
  font-size: 0.8rem; outline: none; cursor: pointer;
}
.btn-primary {
  display: flex; align-items: center; gap: 0.5rem;
  background: var(--accent); color: #000; border: none; border-radius: 7px;
  padding: 0.5rem 1.2rem; font-weight: 700; font-size: 0.82rem;
  letter-spacing: 0.05em; transition: all 0.2s; white-space: nowrap; cursor: pointer;
}
.btn-primary:hover:not(:disabled) { filter: brightness(1.15); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.spinner {
  width: 11px; height: 11px; border: 2px solid #00000044;
  border-top-color: #000; border-radius: 50%;
  animation: spin 0.6s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Suggestions */
.suggestions { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.sug-label { font-size: 0.72rem; color: var(--muted); flex-shrink: 0; }
.sug-pill {
  background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: 20px; padding: 0.25rem 0.8rem;
  font-size: 0.76rem; color: var(--text); cursor: pointer; transition: all 0.15s;
}
.sug-pill:hover { border-color: var(--accent); color: var(--accent); }

.error-bar {
  background: #ff4d4d15; border: 1px solid #ff4d4d44;
  color: var(--danger); border-radius: 8px; padding: 0.7rem 1rem; font-size: 0.85rem;
}

/* Results */
.results-section { display: flex; flex-direction: column; gap: 1rem; }

/* Speed comparison */
.speed-comparison {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1rem 1.2rem;
}
.speed-title { font-size: 0.8rem; font-weight: 600; margin-bottom: 0.8rem; }
.speed-bars  { display: flex; flex-direction: column; gap: 0.6rem; }
.speed-row   { display: flex; align-items: center; gap: 0.7rem; }
.speed-model { font-size: 0.78rem; width: 130px; flex-shrink: 0; }
.speed-track { flex: 1; height: 8px; background: var(--bg-hover); border-radius: 4px; overflow: hidden; }
.speed-fill  { height: 100%; border-radius: 4px; transition: width 0.6s ease; }
.speed-ms    { font-size: 0.75rem; font-weight: 600; width: 70px; text-align: right; }

.speed-fast   { background: var(--ok);     color: var(--ok); }
.speed-medium { background: var(--warn);   color: var(--warn); }
.speed-slow   { background: var(--danger); color: var(--danger); }
.speed-na     { background: var(--muted);  color: var(--muted); }

/* Risk overview */
.risk-overview { display: flex; gap: 0.6rem; flex-wrap: wrap; }
.risk-chip {
  display: flex; align-items: center; gap: 0.5rem;
  border-radius: 8px; padding: 0.45rem 0.9rem;
  font-size: 0.82rem; border: 1px solid transparent;
}
.risk-model { color: inherit; opacity: 0.8; font-size: 0.75rem; }
.risk-val   { font-weight: 800; font-size: 0.9rem; }
.risk-high   { background: #ff4d4d18; border-color: #ff4d4d55; color: var(--danger); }
.risk-medium { background: #ffb34718; border-color: #ffb34755; color: var(--warn); }
.risk-low    { background: #39d98a18; border-color: #39d98a55; color: var(--ok); }
.risk-na     { background: var(--bg-card); border-color: var(--border); color: var(--muted); }

/* Compare grid */
.compare-grid { display: grid; gap: 0.8rem; }
.result-col {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; overflow: hidden;
  display: flex; flex-direction: column;
}
.col-header {
  display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;
  padding: 0.7rem 1rem; border-bottom: 1px solid var(--border);
  background: var(--bg-hover);
}
.col-model    { font-size: 0.85rem; font-weight: 700; }
.col-provider { font-size: 0.7rem; color: var(--muted); }
.col-ms       { font-size: 0.72rem; font-weight: 600; margin-left: auto; }

.result-section { padding: 0.8rem 1rem; border-bottom: 1px solid var(--border); }
.result-section:last-child { border-bottom: none; }
.result-label  { font-size: 0.7rem; letter-spacing: 0.06em; color: var(--muted); margin-bottom: 0.4rem; font-weight: 600; }
.warn-label { color: var(--warn); }
.ok-label   { color: var(--ok); }
.result-text { font-size: 0.82rem; line-height: 1.6; }
.result-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0.35rem; }
.result-list li { font-size: 0.8rem; line-height: 1.5; display: flex; gap: 0.4rem; }
.result-list li::before { content: "›"; color: var(--accent); flex-shrink: 0; }

.col-error { padding: 1rem; color: var(--danger); font-size: 0.82rem; }
.col-error-hint { margin-top: 0.4rem; font-size: 0.76rem; color: var(--muted); }
.col-error-hint code { color: var(--accent); background: var(--bg-hover); padding: 0.1rem 0.3rem; border-radius: 3px; }

/* Summary table */
.summary-table-wrap {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; overflow: hidden;
}
.summary-table-title {
  padding: 0.7rem 1rem; border-bottom: 1px solid var(--border);
  font-size: 0.82rem; font-weight: 600;
}
.summary-table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
th {
  text-align: left; padding: 0.5rem 0.8rem;
  border-bottom: 1px solid var(--border); color: var(--muted);
  background: var(--bg-hover); font-size: 0.75rem; letter-spacing: 0.04em;
}
td { padding: 0.45rem 0.8rem; border-bottom: 1px solid var(--border); }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg-hover); }

.risk-chip-sm {
  display: inline-block; padding: 0.15rem 0.5rem;
  border-radius: 4px; font-size: 0.72rem; font-weight: 700;
}
</style>