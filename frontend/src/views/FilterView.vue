<template>
  <div class="filter-view">

    <div class="page-header">
      <h1>Filter Logs</h1>
      <p class="subtitle">Filter log records by IP address, time window, protocol or action.</p>
    </div>

    <!-- Filter form -->
    <div class="filter-card">
      <div class="filter-grid">

        <div class="field">
          <label>Source IP</label>
          <input v-model="filters.src_ip" placeholder="e.g. 192.168.0" @keydown.enter="runFilter" />
        </div>

        <div class="field">
          <label>Destination IP</label>
          <input v-model="filters.dst_ip" placeholder="e.g. 10.0.0.5" @keydown.enter="runFilter" />
        </div>

        <div class="field">
          <label>Time Window</label>
          <select v-model="filters.hours">
            <option :value="null">All time</option>
            <option :value="1">Last 1 hour</option>
            <option :value="6">Last 6 hours</option>
            <option :value="24">Last 24 hours</option>
            <option :value="168">Last 7 days</option>
            <option :value="720">Last 30 days</option>
          </select>
        </div>

        <div class="field">
          <label>Protocol</label>
          <select v-model="filters.protocol">
            <option value="">Any</option>
            <option>TCP</option>
            <option>UDP</option>
            <option>ICMP</option>
          </select>
        </div>

        <div class="field">
          <label>Action / Flag</label>
          <select v-model="filters.action">
            <option value="">Any</option>
            <option>SYN</option>
            <option>PSH</option>
            <option>ACK</option>
            <option>FIN</option>
            <option>RST</option>
          </select>
        </div>

      </div>

      <div class="filter-actions">
        <button class="btn-primary" :disabled="loading" @click="runFilter">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? 'Filtering...' : 'Apply Filter' }}
        </button>
        <button class="btn-clear" @click="clearFilters">Clear</button>
      </div>
    </div>

    <div v-if="error" class="error-bar">⚠ {{ error }}</div>

    <!-- Results -->
    <div v-if="results !== null">
      <div class="results-header">
        <span class="results-count">{{ results.count }} record{{ results.count !== 1 ? 's' : '' }} found</span>
      </div>

      <div v-if="results.count === 0" class="empty">
        No records match the selected filters.
      </div>

      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Src IP</th>
              <th>Dst IP</th>
              <th>Src Port</th>
              <th>Dst Port</th>
              <th>Protocol</th>
              <th>Bytes</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in results.records" :key="i" :class="rowClass(r)">
              <td>{{ r.timestamp ?? '—' }}</td>
              <td class="ip">{{ r.src_ip ?? '—' }}</td>
              <td class="ip">{{ r.dst_ip ?? '—' }}</td>
              <td>{{ r.src_port ?? '—' }}</td>
              <td>{{ r.dst_port ?? '—' }}</td>
              <td><span class="proto-chip">{{ r.protocol }}</span></td>
              <td>{{ r.bytes ?? '—' }}</td>
              <td><span class="action-chip" :class="actionClass(r.action)">{{ r.action }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const loading = ref(false)
const error   = ref(null)
const results = ref(null)

const filters = ref({
  src_ip:   '',
  dst_ip:   '',
  hours:    null,
  protocol: '',
  action:   '',
})

async function runFilter() {
  loading.value = true
  error.value   = null
  try {
    const params = {}
    if (filters.value.src_ip)   params.src_ip   = filters.value.src_ip
    if (filters.value.dst_ip)   params.dst_ip   = filters.value.dst_ip
    if (filters.value.hours)    params.hours     = filters.value.hours
    if (filters.value.protocol) params.protocol  = filters.value.protocol
    if (filters.value.action)   params.action    = filters.value.action

    const { data } = await axios.get('/logs/filter', { params })
    results.value = data
  } catch (e) {
    error.value = e.response?.data?.detail ?? 'Filter failed.'
  } finally {
    loading.value = false
  }
}

function clearFilters() {
  filters.value = { src_ip: '', dst_ip: '', hours: null, protocol: '', action: '' }
  results.value = null
  error.value   = null
}

function rowClass(r) {
  if (r.action === 'PSH') return 'row-warn'
  if (r.dst_port === 22 || r.dst_port === 23) return 'row-danger'
  return ''
}

function actionClass(action) {
  if (action === 'PSH') return 'action-warn'
  if (action === 'SYN') return 'action-info'
  if (action === 'ACK') return 'action-ok'
  return ''
}
</script>

<style scoped>
.filter-view { display: flex; flex-direction: column; gap: 1.5rem; }

.page-header h1 {
  font-family: var(--font-head); font-size: 1.8rem;
  font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }

.filter-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.5rem;
  display: flex; flex-direction: column; gap: 1.2rem;
}

.filter-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}

.field { display: flex; flex-direction: column; gap: 0.4rem; }
.field label { font-size: 0.72rem; letter-spacing: 0.08em; color: var(--muted); }
.field input, .field select {
  background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: 7px; padding: 0.5rem 0.8rem;
  color: var(--text); font-size: 0.85rem; outline: none;
  transition: border-color 0.2s;
}
.field input:focus, .field select:focus { border-color: var(--accent); }
.field input::placeholder { color: var(--muted); }

.filter-actions { display: flex; gap: 0.8rem; align-items: center; }

.btn-primary {
  display: flex; align-items: center; gap: 0.5rem;
  background: var(--accent); color: #000; border: none;
  border-radius: 8px; padding: 0.6rem 1.6rem;
  font-weight: 700; font-size: 0.85rem; letter-spacing: 0.05em;
  transition: all 0.2s;
}
.btn-primary:hover:not(:disabled) { filter: brightness(1.15); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-clear {
  background: none; border: 1px solid var(--border);
  color: var(--muted); border-radius: 8px; padding: 0.6rem 1.2rem;
  font-size: 0.82rem; transition: all 0.2s;
}
.btn-clear:hover { border-color: var(--danger); color: var(--danger); }

.spinner {
  width: 11px; height: 11px; border: 2px solid #00000044;
  border-top-color: #000; border-radius: 50%;
  animation: spin 0.6s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

.results-header {
  display: flex; align-items: center; gap: 1rem;
  margin-bottom: 0.8rem;
}
.results-count {
  font-size: 0.82rem; color: var(--muted);
}

.empty {
  background: var(--bg-card); border: 1px dashed var(--border);
  border-radius: 10px; padding: 2rem; text-align: center;
  color: var(--muted); font-size: 0.85rem;
}

.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.78rem; }
th {
  text-align: left; color: var(--muted); padding: 0.5rem 0.8rem;
  border-bottom: 1px solid var(--border); white-space: nowrap;
  letter-spacing: 0.05em; background: var(--bg-card);
}
td {
  padding: 0.45rem 0.8rem; border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg-hover); }

.row-warn td  { background: #ffb34708; }
.row-danger td { background: #ff4d4d08; }

.ip { color: var(--accent); font-size: 0.75rem; }

.proto-chip {
  background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: 4px; padding: 0.1rem 0.4rem; font-size: 0.72rem;
}

.action-chip {
  border-radius: 4px; padding: 0.1rem 0.5rem;
  font-size: 0.72rem; font-weight: 700;
}
.action-warn { background: #ffb34722; color: var(--warn); border: 1px solid #ffb34744; }
.action-info { background: #00e5ff22; color: var(--accent); border: 1px solid #00e5ff44; }
.action-ok   { background: #39d98a22; color: var(--ok);   border: 1px solid #39d98a44; }

.error-bar {
  background: #ff4d4d15; border: 1px solid #ff4d4d44;
  color: var(--danger); border-radius: 8px; padding: 0.7rem 1rem; font-size: 0.85rem;
}
</style>