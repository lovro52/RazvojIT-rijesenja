<template>
  <div class="compare-view">

    <div class="page-header">
      <h1>Usporedba pretraga</h1>
      <p class="subtitle">
        Usporedba klasičnog <strong>keyword</strong> pretraživanja i naprednog <strong>semantičkog</strong> pretraživanja.
      </p>
    </div>

    <!-- Explanation banner -->
    <div class="info-banner">
      <div class="info-item">
        <span class="info-icon kw">KW</span>
        <div>
          <div class="info-title">Keyword pretraga</div>
          <div class="info-desc">Traži točno podudaranje teksta u logovima. Brzo, ali propušta kontekstualno slične rezultate.</div>
        </div>
      </div>
      <div class="info-divider">vs</div>
      <div class="info-item">
        <span class="info-icon sem">SEM</span>
        <div>
          <div class="info-title">Semantička pretraga (RAG)</div>
          <div class="info-desc">Razumije značenje upita i pronalazi kontekstualno relevantne logove čak i bez točnog podudaranja.</div>
        </div>
      </div>
    </div>

    <!-- Search bar -->
    <div class="search-bar">
      <span class="search-icon">⌕</span>
      <input
        v-model="query"
        type="text"
        placeholder="e.g. suspicious SSH activity"
        @keydown.enter="runCompare"
      />
      <select v-model="topK" class="topk-select">
        <option :value="3">top 3</option>
        <option :value="5">top 5</option>
        <option :value="10">top 10</option>
      </select>
      <button class="btn-primary" :disabled="!query.trim() || loading" @click="runCompare">
        <span v-if="loading" class="spinner"></span>
        {{ loading ? 'Pretražujem...' : 'Usporedi' }}
      </button>
    </div>

    <div v-if="error" class="error-bar">⚠ {{ error }}</div>

    <!-- Results -->
    <div v-if="result" class="results-grid">

      <!-- Keyword results -->
      <div class="result-col">
        <div class="col-header kw-header">
          <span class="col-badge kw">KW</span>
          <span class="col-title">Keyword pretraga</span>
          <span class="col-meta">{{ result.keyword.count }} rezultata · {{ result.keyword.time_ms }} ms</span>
        </div>

        <div v-if="result.keyword.count === 0" class="no-results">
          Nema rezultata za ovaj upit.
        </div>

        <div v-else class="record-list">
          <div
            v-for="(r, i) in result.keyword.results"
            :key="i"
            class="record-card kw-card"
          >
            <div class="record-message">{{ r.message }}</div>
            <div class="record-meta">
              <span class="meta-chip">{{ r.src_ip }}</span>
              <span class="meta-chip">→ {{ r.dst_ip }}</span>
              <span class="meta-chip action" :class="actionClass(r.action)">{{ r.action }}</span>
              <span class="meta-chip">port {{ r.dst_port }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Semantic results -->
      <div class="result-col">
        <div class="col-header sem-header">
          <span class="col-badge sem">SEM</span>
          <span class="col-title">Semantička pretraga</span>
          <span class="col-meta">{{ result.semantic.count }} rezultata · {{ result.semantic.time_ms }} ms</span>
        </div>

        <div v-if="result.semantic.count === 0" class="no-results">
          Nema rezultata za ovaj upit.
        </div>

        <div v-else class="record-list">
          <div
            v-for="(r, i) in result.semantic.results"
            :key="i"
            class="record-card sem-card"
          >
            <div class="similarity-bar">
              <span class="sim-label">Sličnost</span>
              <div class="sim-track">
                <div class="sim-fill" :style="{ width: similarityPct(r.distance) + '%' }"></div>
              </div>
              <span class="sim-pct">{{ similarityPct(r.distance) }}%</span>
            </div>
            <div class="record-message">{{ r.document }}</div>
            <div class="record-meta">
              <span class="meta-chip">{{ r.metadata.src_ip }}</span>
              <span class="meta-chip">→ {{ r.metadata.dst_ip }}</span>
              <span class="meta-chip action" :class="actionClass(r.metadata.action)">{{ r.metadata.action }}</span>
              <span class="meta-chip">port {{ r.metadata.dst_port }}</span>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- Comparison summary -->
    <div v-if="result" class="summary-card">
      <div class="summary-title">📊 Zaključak usporedbe</div>
      <div class="summary-grid">
        <div class="summary-item">
          <span class="summary-label">Keyword pronašao</span>
          <span class="summary-value">{{ result.keyword.count }} logova</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Semantika pronašla</span>
          <span class="summary-value">{{ result.semantic.count }} logova</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Keyword vrijeme</span>
          <span class="summary-value">{{ result.keyword.time_ms }} ms</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">Semantika vrijeme</span>
          <span class="summary-value">{{ result.semantic.time_ms }} ms</span>
        </div>
        <div class="summary-item wide">
          <span class="summary-label">Razlika u rezultatima</span>
          <span class="summary-value" :class="diffClass">
            {{ diffText }}
          </span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import axios from 'axios'

const query   = ref('')
const topK    = ref(5)
const loading = ref(false)
const error   = ref(null)
const result  = ref(null)

const diffClass = computed(() => {
  if (!result.value) return ''
  const diff = result.value.semantic.count - result.value.keyword.count
  if (diff > 0) return 'diff-more'
  if (diff < 0) return 'diff-less'
  return ''
})

const diffText = computed(() => {
  if (!result.value) return ''
  const kw  = result.value.keyword.count
  const sem = result.value.semantic.count

  // Check overlap by comparing messages
  const kwMessages  = new Set(result.value.keyword.results.map(r => r.message))
  const semMessages = new Set(result.value.semantic.results.map(r => r.document))
  const overlap = [...kwMessages].filter(m => semMessages.has(m)).length
  const unique  = sem - overlap

  if (overlap === sem && overlap === kw) return 'Identični rezultati'
  if (unique > 0) return `Semantika pronašla ${unique} dodatnih relevantnih logova koje keyword nije`
  if (sem < kw)   return `Keyword pronašao više rezultata (${kw - sem} više)`
  return 'Slični rezultati'
})

async function runCompare() {
  if (!query.value.trim()) return
  loading.value = true
  error.value   = null
  result.value  = null
  try {
    const { data } = await axios.get('/logs/compare', {
      params: { q: query.value, top_k: topK.value }
    })
    result.value = data
  } catch (e) {
    error.value = e.response?.data?.detail ?? 'Pretraga nije uspjela.'
  } finally {
    loading.value = false
  }
}

function similarityPct(distance) {
  // Convert distance to similarity percentage (lower distance = higher similarity)
  return Math.max(0, Math.round((1 - distance / 2) * 100))
}

function actionClass(action) {
  if (action === 'PSH') return 'action-warn'
  if (action === 'SYN') return 'action-info'
  if (action === 'ACK') return 'action-ok'
  return ''
}
</script>

<style scoped>
.compare-view { display: flex; flex-direction: column; gap: 1.5rem; }

.page-header h1 {
  font-family: var(--font-head); font-size: 1.8rem;
  font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }
.subtitle strong { color: var(--text); }

/* Info banner */
.info-banner {
  display: flex; align-items: center; gap: 1.5rem;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.2rem 1.5rem; flex-wrap: wrap;
}
.info-item { display: flex; align-items: flex-start; gap: 0.8rem; flex: 1; min-width: 200px; }
.info-icon {
  width: 36px; height: 36px; border-radius: 8px; display: flex;
  align-items: center; justify-content: center; font-size: 0.7rem;
  font-weight: 800; letter-spacing: 0.05em; flex-shrink: 0;
}
.info-icon.kw  { background: #64748b22; color: var(--muted); border: 1px solid #64748b44; }
.info-icon.sem { background: var(--accent-dim); color: var(--accent); border: 1px solid #00e5ff44; }
.info-title { font-size: 0.85rem; font-weight: 600; margin-bottom: 0.2rem; }
.info-desc  { font-size: 0.78rem; color: var(--muted); line-height: 1.5; }
.info-divider {
  font-family: var(--font-head); font-size: 1.2rem; font-weight: 800;
  color: var(--border); flex-shrink: 0;
}

/* Search bar */
.search-bar {
  display: flex; align-items: center; gap: 0.6rem;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 10px; padding: 0.5rem 0.8rem; transition: border-color 0.2s;
}
.search-bar:focus-within { border-color: var(--accent); }
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
  background: var(--accent); color: #000; border: none;
  border-radius: 7px; padding: 0.5rem 1.2rem;
  font-weight: 700; font-size: 0.82rem; letter-spacing: 0.05em;
  transition: all 0.2s; white-space: nowrap;
}
.btn-primary:hover:not(:disabled) { filter: brightness(1.15); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
.spinner {
  width: 11px; height: 11px; border: 2px solid #00000044;
  border-top-color: #000; border-radius: 50%;
  animation: spin 0.6s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Results grid */
.results-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 720px) { .results-grid { grid-template-columns: 1fr; } }

.result-col { display: flex; flex-direction: column; gap: 0.6rem; }

.col-header {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.7rem 1rem; border-radius: 10px; flex-wrap: wrap;
}
.kw-header  { background: #64748b18; border: 1px solid #64748b44; }
.sem-header { background: var(--accent-dim); border: 1px solid #00e5ff33; }

.col-badge {
  padding: 0.2rem 0.5rem; border-radius: 4px;
  font-size: 0.68rem; font-weight: 800; letter-spacing: 0.08em; flex-shrink: 0;
}
.col-badge.kw  { background: #64748b33; color: var(--muted); }
.col-badge.sem { background: #00e5ff22; color: var(--accent); }
.col-title { font-size: 0.85rem; font-weight: 600; }
.col-meta  { font-size: 0.75rem; color: var(--muted); margin-left: auto; }

.no-results {
  background: var(--bg-card); border: 1px dashed var(--border);
  border-radius: 8px; padding: 1.5rem; text-align: center;
  color: var(--muted); font-size: 0.82rem;
}

.record-list { display: flex; flex-direction: column; gap: 0.5rem; }

.record-card {
  border-radius: 8px; padding: 0.8rem 1rem;
  display: flex; flex-direction: column; gap: 0.5rem;
}
.kw-card  { background: var(--bg-card); border: 1px solid var(--border); }
.sem-card { background: var(--bg-card); border: 1px solid #00e5ff22; }

.record-message { font-size: 0.8rem; line-height: 1.5; }

.record-meta { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.meta-chip {
  background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: 4px; padding: 0.1rem 0.4rem; font-size: 0.7rem; color: var(--muted);
}
.meta-chip.action { font-weight: 700; }
.action-warn  { background: #ffb34722; color: var(--warn);   border-color: #ffb34744; }
.action-info  { background: #00e5ff22; color: var(--accent); border-color: #00e5ff44; }
.action-ok    { background: #39d98a22; color: var(--ok);     border-color: #39d98a44; }

/* Similarity bar */
.similarity-bar {
  display: flex; align-items: center; gap: 0.5rem;
}
.sim-label { font-size: 0.68rem; color: var(--muted); flex-shrink: 0; }
.sim-track {
  flex: 1; height: 4px; background: var(--bg-hover);
  border-radius: 2px; overflow: hidden;
}
.sim-fill { height: 100%; background: var(--accent); border-radius: 2px; transition: width 0.4s ease; }
.sim-pct  { font-size: 0.7rem; color: var(--accent); flex-shrink: 0; width: 30px; text-align: right; }

/* Summary card */
.summary-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.2rem 1.5rem;
}
.summary-title { font-size: 0.85rem; font-weight: 600; margin-bottom: 1rem; }
.summary-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 0.8rem;
}
.summary-item { display: flex; flex-direction: column; gap: 0.2rem; }
.summary-item.wide { grid-column: 1 / -1; }
.summary-label { font-size: 0.72rem; color: var(--muted); letter-spacing: 0.04em; }
.summary-value { font-size: 0.9rem; font-weight: 600; }
.diff-more { color: var(--ok); }
.diff-less { color: var(--warn); }

.error-bar {
  background: #ff4d4d15; border: 1px solid #ff4d4d44;
  color: var(--danger); border-radius: 8px; padding: 0.7rem 1rem; font-size: 0.85rem;
}
</style>