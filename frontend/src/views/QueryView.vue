<template>
  <div class="query-view">

    <div class="page-header">
      <h1>Query Logs</h1>
      <p class="subtitle">Ask a security question — the system retrieves relevant logs and generates an analysis.</p>
    </div>

    <!-- Search bar -->
    <div class="search-bar">
      <span class="search-icon">⌕</span>
      <input
        v-model="query"
        type="text"
        placeholder="e.g. Are there any suspicious connections?"
        @keydown.enter="runQuery"
      />
      <select v-model="topK" class="topk-select">
        <option :value="3">top 3</option>
        <option :value="5">top 5</option>
        <option :value="10">top 10</option>
      </select>
      <button class="btn-primary" :disabled="!query.trim() || loading" @click="runQuery">
        <span v-if="loading" class="spinner"></span>
        {{ loading ? 'Analyzing...' : 'Analyze' }}
      </button>
    </div>

    <div v-if="error" class="error-bar">⚠ {{ error }}</div>

    <!-- Report -->
    <div v-if="result" class="results">

      <!-- Risk level banner -->
      <div class="risk-banner" :class="riskClass">
        <div class="risk-left">
          <span class="risk-label">RISK LEVEL</span>
          <span class="risk-value">{{ result.report.risk_level }}</span>
        </div>
        <p class="risk-summary">{{ result.report.summary }}</p>
      </div>

      <div class="grid-2">

        <!-- Key indicators -->
        <div class="card">
          <div class="card-title">
            <span class="card-icon warn">⚑</span> Key Indicators
          </div>
          <ul class="indicator-list">
            <li v-for="(ind, i) in result.report.key_indicators" :key="i">
              <span class="bullet">›</span> {{ ind }}
            </li>
          </ul>
        </div>

        <!-- Recommended actions -->
        <div class="card">
          <div class="card-title">
            <span class="card-icon ok">✓</span> Recommended Actions
          </div>
          <ul class="indicator-list">
            <li v-for="(act, i) in result.report.recommended_actions" :key="i">
              <span class="bullet">›</span> {{ act }}
            </li>
          </ul>
        </div>

      </div>

      <!-- Evidence highlights -->
      <div v-if="result.report.evidence_highlights?.length" class="card">
        <div class="card-title">
          <span class="card-icon accent">◈</span> Evidence Highlights
        </div>
        <div class="evidence-list">
          <div
            v-for="(ev, i) in result.report.evidence_highlights"
            :key="i"
            class="evidence-item"
          >
            <div class="ev-id">{{ ev.id }}</div>
            <div class="ev-reason">{{ ev.reason }}</div>
          </div>
        </div>
      </div>

      <!-- Retrieved log records -->
      <div class="card">
        <div class="card-title">
          <span class="card-icon muted">≡</span> Retrieved Log Records
          <span class="count-badge">{{ result.evidence.length }}</span>
        </div>
        <div class="log-list">
          <div
            v-for="(rec, i) in result.evidence"
            :key="i"
            class="log-item"
          >
            <div class="log-top">
              <span class="log-id">{{ rec.id }}</span>
              <span class="log-dist">dist: {{ rec.distance.toFixed(4) }}</span>
            </div>
            <div class="log-doc">{{ rec.document }}</div>
            <div class="log-meta">
              <span v-for="(val, key) in rec.metadata" :key="key" class="meta-chip">
                <span class="meta-key">{{ key }}</span>
                <span class="meta-val">{{ val }}</span>
              </span>
            </div>
          </div>
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

const riskClass = computed(() => {
  const r = result.value?.report?.risk_level
  if (r === 'HIGH')   return 'risk-high'
  if (r === 'MEDIUM') return 'risk-medium'
  return 'risk-low'
})

async function runQuery() {
  if (!query.value.trim()) return
  loading.value = true
  error.value   = null
  result.value  = null
  try {
    const { data } = await axios.get('/logs/query/rag_local', {
      params: { q: query.value, top_k: topK.value }
    })
    result.value = data
  } catch (e) {
    error.value = e.response?.data?.detail ?? 'Query failed.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.query-view { display: flex; flex-direction: column; gap: 1.5rem; }

.page-header h1 {
  font-family: var(--font-head);
  font-size: 1.8rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }

/* Search bar */
.search-bar {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.5rem 0.8rem;
  transition: border-color 0.2s;
}
.search-bar:focus-within { border-color: var(--accent); }
.search-icon { color: var(--muted); font-size: 1.1rem; flex-shrink: 0; }
.search-bar input {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  color: var(--text);
  font-size: 0.9rem;
  min-width: 0;
}
.search-bar input::placeholder { color: var(--muted); }

.topk-select {
  background: var(--bg-hover);
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 6px;
  padding: 0.3rem 0.5rem;
  font-size: 0.8rem;
  outline: none;
  cursor: pointer;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--accent);
  color: #000;
  border: none;
  border-radius: 7px;
  padding: 0.5rem 1.2rem;
  font-weight: 700;
  font-size: 0.82rem;
  letter-spacing: 0.05em;
  transition: all 0.2s;
  white-space: nowrap;
}
.btn-primary:hover:not(:disabled) { filter: brightness(1.15); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

.spinner {
  width: 11px; height: 11px;
  border: 2px solid #00000044;
  border-top-color: #000;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Risk banner */
.risk-banner {
  border-radius: 12px;
  padding: 1.2rem 1.5rem;
  display: flex;
  align-items: flex-start;
  gap: 2rem;
  flex-wrap: wrap;
}
.risk-high   { background: #ff4d4d18; border: 1px solid #ff4d4d55; }
.risk-medium { background: #ffb34718; border: 1px solid #ffb34755; }
.risk-low    { background: #39d98a18; border: 1px solid #39d98a55; }

.risk-left { display: flex; flex-direction: column; gap: 0.2rem; flex-shrink: 0; }
.risk-label { font-size: 0.68rem; letter-spacing: 0.12em; color: var(--muted); }
.risk-value {
  font-family: var(--font-head);
  font-size: 1.6rem;
  font-weight: 800;
  letter-spacing: 0.05em;
}
.risk-high   .risk-value { color: var(--danger); }
.risk-medium .risk-value { color: var(--warn); }
.risk-low    .risk-value { color: var(--ok); }

.risk-summary { color: var(--text); font-size: 0.88rem; line-height: 1.7; padding-top: 0.2rem; }

/* Grid */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 680px) { .grid-2 { grid-template-columns: 1fr; } }

/* Cards */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.8rem 1.2rem;
  border-bottom: 1px solid var(--border);
  font-size: 0.82rem;
  letter-spacing: 0.06em;
  font-weight: 600;
}
.card-icon { font-size: 0.9rem; }
.card-icon.warn   { color: var(--warn); }
.card-icon.ok     { color: var(--ok); }
.card-icon.accent { color: var(--accent); }
.card-icon.muted  { color: var(--muted); }

.count-badge {
  margin-left: auto;
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.1rem 0.5rem;
  font-size: 0.72rem;
  color: var(--muted);
}

/* Indicators */
.indicator-list {
  list-style: none;
  padding: 0.8rem 1.2rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.indicator-list li { display: flex; gap: 0.5rem; font-size: 0.83rem; line-height: 1.5; }
.bullet { color: var(--accent); flex-shrink: 0; }

/* Evidence */
.evidence-list { padding: 0.8rem 1.2rem; display: flex; flex-direction: column; gap: 0.6rem; }
.evidence-item {
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.7rem 1rem;
}
.ev-id { font-size: 0.75rem; color: var(--accent); margin-bottom: 0.2rem; }
.ev-reason { font-size: 0.82rem; color: var(--text); }

/* Log records */
.log-list { padding: 0.8rem 1.2rem; display: flex; flex-direction: column; gap: 0.8rem; }
.log-item {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.8rem 1rem;
  background: var(--bg-hover);
}
.log-top {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.4rem;
}
.log-id { font-size: 0.75rem; color: var(--accent); }
.log-dist { font-size: 0.72rem; color: var(--muted); }
.log-doc { font-size: 0.82rem; margin-bottom: 0.5rem; line-height: 1.5; }
.log-meta { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.meta-chip {
  display: flex;
  gap: 0.2rem;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.1rem 0.5rem;
  font-size: 0.7rem;
}
.meta-key { color: var(--muted); }
.meta-val { color: var(--text); }

/* Error */
.error-bar {
  background: #ff4d4d15;
  border: 1px solid #ff4d4d44;
  color: var(--danger);
  border-radius: 8px;
  padding: 0.7rem 1rem;
  font-size: 0.85rem;
}
</style>