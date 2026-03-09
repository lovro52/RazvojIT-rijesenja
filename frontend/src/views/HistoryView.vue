<template>
  <div class="history-view">

    <div class="page-header">
      <h1>Povijest upita</h1>
      <p class="subtitle">Svi RAG upiti i generirani sigurnosni izvještaji.</p>
    </div>

    <div class="toolbar">
      <button class="btn-refresh" @click="loadHistory">
        <span :class="{ spinning: loading }">↻</span> Refresh
      </button>
      <span v-if="history.length" class="total-count">{{ history.length }} upita ukupno</span>
    </div>

    <div v-if="loading" class="loading">Učitavanje...</div>

    <div v-else-if="history.length === 0" class="empty">
      <p>Nema povijesti upita. Idi na <RouterLink to="/query">Query</RouterLink> i postavi pitanje.</p>
    </div>

    <div v-else class="history-list">
      <div
        v-for="item in history"
        :key="item.id"
        class="history-card"
        :class="riskClass(item.risk_level)"
        @click="toggle(item.id)"
      >
        <!-- Header -->
        <div class="card-header">
          <span class="risk-badge" :class="riskClass(item.risk_level)">
            {{ item.risk_level ?? '—' }}
          </span>
          <span class="query-text">{{ item.query }}</span>
          <span class="queried-at">{{ formatDate(item.queried_at) }}</span>
          <span class="chevron">{{ expanded === item.id ? '▲' : '▼' }}</span>
        </div>

        <!-- Summary always visible -->
        <div class="card-summary">{{ item.summary ?? 'Nema sažetka.' }}</div>

        <!-- Expanded detail -->
        <div v-if="expanded === item.id" class="card-detail">
          <div class="detail-grid">

            <div class="detail-section">
              <div class="detail-label"><span class="warn">⚑</span> Ključni indikatori</div>
              <ul>
                <li v-for="(ind, i) in item.key_indicators" :key="i">
                  <span class="bullet">›</span> {{ ind }}
                </li>
                <li v-if="!item.key_indicators.length" class="muted">Nema indikatora.</li>
              </ul>
            </div>

            <div class="detail-section">
              <div class="detail-label"><span class="ok">✓</span> Preporučene akcije</div>
              <ul>
                <li v-for="(act, i) in item.recommended_actions" :key="i">
                  <span class="bullet">›</span> {{ act }}
                </li>
                <li v-if="!item.recommended_actions.length" class="muted">Nema preporuka.</li>
              </ul>
            </div>

          </div>

          <div class="detail-meta">
            <span class="meta-chip">top_k: {{ item.top_k }}</span>
            <span class="meta-chip">{{ item.evidence_count }} dokaza</span>
          </div>
        </div>

      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const history  = ref([])
const loading  = ref(false)
const expanded = ref(null)

async function loadHistory() {
  loading.value = true
  try {
    const { data } = await axios.get('/logs/history')
    history.value = data.history
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function toggle(id) {
  expanded.value = expanded.value === id ? null : id
}

function riskClass(level) {
  if (level === 'HIGH')   return 'risk-high'
  if (level === 'MEDIUM') return 'risk-medium'
  if (level === 'LOW')    return 'risk-low'
  return ''
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

onMounted(loadHistory)
</script>

<style scoped>
.history-view { display: flex; flex-direction: column; gap: 1.5rem; }

.page-header h1 {
  font-family: var(--font-head); font-size: 1.8rem;
  font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }

.toolbar { display: flex; align-items: center; gap: 1rem; }

.btn-refresh {
  display: flex; align-items: center; gap: 0.4rem;
  background: var(--bg-card); border: 1px solid var(--border);
  color: var(--muted); border-radius: 7px; padding: 0.45rem 1rem;
  font-size: 0.82rem; transition: all 0.2s; width: fit-content;
}
.btn-refresh:hover { border-color: var(--accent); color: var(--accent); }
.spinning { display: inline-block; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.total-count { font-size: 0.8rem; color: var(--muted); }
.loading     { color: var(--muted); font-size: 0.85rem; }

.empty {
  background: var(--bg-card); border: 1px dashed var(--border);
  border-radius: 12px; padding: 2.5rem; text-align: center;
  color: var(--muted); font-size: 0.85rem;
}
.empty a { color: var(--accent); text-decoration: none; }

.history-list { display: flex; flex-direction: column; gap: 0.8rem; }

.history-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; overflow: hidden; cursor: pointer;
  transition: border-color 0.2s;
}
.history-card:hover { border-color: var(--accent); }
.history-card.risk-high   { border-left: 3px solid var(--danger); }
.history-card.risk-medium { border-left: 3px solid var(--warn); }
.history-card.risk-low    { border-left: 3px solid var(--ok); }

.card-header {
  display: flex; align-items: center; gap: 0.8rem;
  padding: 0.9rem 1.2rem; flex-wrap: wrap;
}

.risk-badge {
  padding: 0.2rem 0.6rem; border-radius: 4px;
  font-size: 0.7rem; font-weight: 800; letter-spacing: 0.08em;
  flex-shrink: 0;
}
.risk-badge.risk-high   { background: #ff4d4d22; color: var(--danger); border: 1px solid #ff4d4d44; }
.risk-badge.risk-medium { background: #ffb34722; color: var(--warn);   border: 1px solid #ffb34744; }
.risk-badge.risk-low    { background: #39d98a22; color: var(--ok);     border: 1px solid #39d98a44; }

.query-text {
  flex: 1; font-size: 0.88rem; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.queried-at { font-size: 0.75rem; color: var(--muted); margin-left: auto; flex-shrink: 0; }
.chevron    { font-size: 0.7rem; color: var(--muted); flex-shrink: 0; }

.card-summary {
  padding: 0 1.2rem 0.9rem;
  font-size: 0.82rem; color: var(--muted); line-height: 1.6;
}

.card-detail {
  border-top: 1px solid var(--border);
  padding: 1rem 1.2rem;
  display: flex; flex-direction: column; gap: 1rem;
}

.detail-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;
}
@media (max-width: 600px) { .detail-grid { grid-template-columns: 1fr; } }

.detail-section { display: flex; flex-direction: column; gap: 0.5rem; }
.detail-label {
  font-size: 0.75rem; font-weight: 600; letter-spacing: 0.06em;
  display: flex; align-items: center; gap: 0.4rem;
}
.warn { color: var(--warn); }
.ok   { color: var(--ok); }

ul { list-style: none; display: flex; flex-direction: column; gap: 0.35rem; }
li { display: flex; gap: 0.4rem; font-size: 0.82rem; line-height: 1.5; }
.bullet { color: var(--accent); flex-shrink: 0; }
.muted  { color: var(--muted); }

.detail-meta { display: flex; gap: 0.5rem; }
.meta-chip {
  background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: 4px; padding: 0.15rem 0.6rem;
  font-size: 0.72rem; color: var(--muted);
}
</style>