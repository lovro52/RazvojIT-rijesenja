<template>
  <div class="dashboard">

    <div class="page-header">
      <h1>Dashboard</h1>
      <p class="subtitle">Pregled stanja sustava i statistike mrežnih logova.</p>
    </div>

    <div v-if="loading" class="loading">Učitavanje...</div>

    <template v-else-if="stats">

      <!-- Stat cards -->
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-icon accent">▣</div>
          <div class="stat-body">
            <div class="stat-value">{{ stats.total_records }}</div>
            <div class="stat-label">Ukupno logova</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon ok">↑</div>
          <div class="stat-body">
            <div class="stat-value">{{ stats.total_files }}</div>
            <div class="stat-label">Uploadanih fajlova</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon warn">⬡</div>
          <div class="stat-body">
            <div class="stat-value">{{ stats.indexed_files }}</div>
            <div class="stat-label">Indeksiranih fajlova</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon danger">⚑</div>
          <div class="stat-body">
            <div class="stat-value">{{ pshCount }}</div>
            <div class="stat-label">PSH akcija (rizično)</div>
          </div>
        </div>
      </div>

      <div class="grid-2">

        <!-- Protocol distribution -->
        <div class="card">
          <div class="card-title">
            <span class="card-icon accent">◈</span> Raspodjela protokola
          </div>
          <div class="bar-list">
            <div v-for="p in stats.protocol_dist" :key="p.protocol" class="bar-item">
              <span class="bar-label">{{ p.protocol }}</span>
              <div class="bar-track">
                <div
                  class="bar-fill accent-fill"
                  :style="{ width: pct(p.count, maxProtocol) + '%' }"
                ></div>
              </div>
              <span class="bar-count">{{ p.count }}</span>
            </div>
          </div>
        </div>

        <!-- Action distribution -->
        <div class="card">
          <div class="card-title">
            <span class="card-icon warn">⚑</span> Raspodjela akcija / flagova
          </div>
          <div class="bar-list">
            <div v-for="a in stats.action_dist" :key="a.action" class="bar-item">
              <span class="bar-label">{{ a.action }}</span>
              <div class="bar-track">
                <div
                  class="bar-fill"
                  :class="actionFillClass(a.action)"
                  :style="{ width: pct(a.count, maxAction) + '%' }"
                ></div>
              </div>
              <span class="bar-count">{{ a.count }}</span>
            </div>
          </div>
        </div>

        <!-- Top source IPs -->
        <div class="card">
          <div class="card-title">
            <span class="card-icon danger">⊙</span> Top izvorne IP adrese
          </div>
          <div class="rank-list">
            <div v-for="(ip, i) in stats.top_src_ips" :key="ip.src_ip" class="rank-item">
              <span class="rank-num">{{ i + 1 }}</span>
              <span class="rank-value ip">{{ ip.src_ip }}</span>
              <div class="bar-track small">
                <div
                  class="bar-fill danger-fill"
                  :style="{ width: pct(ip.count, stats.top_src_ips[0].count) + '%' }"
                ></div>
              </div>
              <span class="bar-count">{{ ip.count }}</span>
            </div>
          </div>
        </div>

        <!-- Top destination ports -->
        <div class="card">
          <div class="card-title">
            <span class="card-icon ok">⊟</span> Top odredišni portovi
          </div>
          <div class="rank-list">
            <div v-for="(p, i) in stats.top_dst_ports" :key="p.dst_port" class="rank-item">
              <span class="rank-num">{{ i + 1 }}</span>
              <span class="rank-value">
                {{ p.dst_port }}
                <span class="port-hint">{{ portHint(p.dst_port) }}</span>
              </span>
              <div class="bar-track small">
                <div
                  class="bar-fill ok-fill"
                  :style="{ width: pct(p.count, stats.top_dst_ports[0].count) + '%' }"
                ></div>
              </div>
              <span class="bar-count">{{ p.count }}</span>
            </div>
          </div>
        </div>

      </div>

      <!-- Recent uploads -->
      <div class="card">
        <div class="card-title">
          <span class="card-icon accent">↑</span> Nedavno uploadani fajlovi
        </div>
        <div class="recent-list">
          <div v-for="f in stats.recent_files" :key="f.filename" class="recent-item">
            <div class="recent-name">{{ f.filename }}</div>
            <div class="recent-meta">
              <span class="tag" :class="f.indexed ? 'tag-ok' : 'tag-warn'">
                {{ f.indexed ? '✓ Indexed' : '⏳ Not indexed' }}
              </span>
              <span class="meta-text">{{ f.rows }} redova</span>
              <span class="meta-text">{{ formatDate(f.uploaded_at) }}</span>
            </div>
          </div>
        </div>
      </div>

    </template>

    <div v-if="error" class="error-bar">⚠ {{ error }}</div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const stats   = ref(null)
const loading = ref(false)
const error   = ref(null)

const maxProtocol = computed(() =>
  stats.value ? Math.max(...stats.value.protocol_dist.map(p => p.count), 1) : 1
)
const maxAction = computed(() =>
  stats.value ? Math.max(...stats.value.action_dist.map(a => a.count), 1) : 1
)
const pshCount = computed(() => {
  if (!stats.value) return 0
  const psh = stats.value.action_dist.find(a => a.action === 'PSH')
  return psh ? psh.count : 0
})

function pct(val, max) {
  return max === 0 ? 0 : Math.round((val / max) * 100)
}

function actionFillClass(action) {
  if (action === 'PSH') return 'warn-fill'
  if (action === 'SYN') return 'accent-fill'
  if (action === 'ACK') return 'ok-fill'
  return 'muted-fill'
}

function portHint(port) {
  const hints = { 22: 'SSH', 23: 'Telnet', 80: 'HTTP', 443: 'HTTPS', 3306: 'MySQL', 3389: 'RDP', 8080: 'HTTP-alt' }
  return hints[port] ? `(${hints[port]})` : ''
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

async function loadStats() {
  loading.value = true
  error.value   = null
  try {
    const { data } = await axios.get('/logs/dashboard')
    stats.value = data
  } catch (e) {
    error.value = 'Greška pri učitavanju statistika.'
  } finally {
    loading.value = false
  }
}

onMounted(loadStats)
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 1.5rem; }

.page-header h1 {
  font-family: var(--font-head); font-size: 1.8rem;
  font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }
.loading  { color: var(--muted); font-size: 0.85rem; }

/* Stat cards */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
}
.stat-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.2rem 1.4rem;
  display: flex; align-items: center; gap: 1rem;
  transition: border-color 0.2s;
}
.stat-card:hover { border-color: var(--accent); }
.stat-icon {
  font-size: 1.4rem; width: 2.4rem; height: 2.4rem;
  display: flex; align-items: center; justify-content: center;
  border-radius: 8px; flex-shrink: 0;
}
.stat-icon.accent { color: var(--accent); background: var(--accent-dim); }
.stat-icon.ok     { color: var(--ok);     background: #39d98a22; }
.stat-icon.warn   { color: var(--warn);   background: #ffb34722; }
.stat-icon.danger { color: var(--danger); background: #ff4d4d22; }

.stat-body { display: flex; flex-direction: column; gap: 0.2rem; }
.stat-value { font-family: var(--font-head); font-size: 1.8rem; font-weight: 800; line-height: 1; }
.stat-label { font-size: 0.75rem; color: var(--muted); letter-spacing: 0.04em; }

/* 2 col grid */
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 700px) { .grid-2 { grid-template-columns: 1fr; } }

/* Cards */
.card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; overflow: hidden;
}
.card-title {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.8rem 1.2rem; border-bottom: 1px solid var(--border);
  font-size: 0.82rem; letter-spacing: 0.06em; font-weight: 600;
}
.card-icon        { font-size: 0.9rem; }
.card-icon.accent { color: var(--accent); }
.card-icon.warn   { color: var(--warn); }
.card-icon.danger { color: var(--danger); }
.card-icon.ok     { color: var(--ok); }

/* Bar charts */
.bar-list { padding: 0.8rem 1.2rem; display: flex; flex-direction: column; gap: 0.6rem; }
.bar-item { display: flex; align-items: center; gap: 0.6rem; }
.bar-label { width: 60px; font-size: 0.78rem; color: var(--text); flex-shrink: 0; }
.bar-track {
  flex: 1; height: 6px; background: var(--bg-hover);
  border-radius: 3px; overflow: hidden;
}
.bar-track.small { height: 4px; }
.bar-fill { height: 100%; border-radius: 3px; transition: width 0.6s ease; }
.accent-fill { background: var(--accent); }
.warn-fill   { background: var(--warn); }
.ok-fill     { background: var(--ok); }
.danger-fill { background: var(--danger); }
.muted-fill  { background: var(--muted); }
.bar-count { font-size: 0.75rem; color: var(--muted); width: 24px; text-align: right; flex-shrink: 0; }

/* Rank list */
.rank-list { padding: 0.8rem 1.2rem; display: flex; flex-direction: column; gap: 0.6rem; }
.rank-item { display: flex; align-items: center; gap: 0.6rem; }
.rank-num {
  width: 18px; font-size: 0.72rem; color: var(--muted);
  flex-shrink: 0; text-align: right;
}
.rank-value {
  width: 130px; font-size: 0.78rem; flex-shrink: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.rank-value.ip { color: var(--accent); }
.port-hint { color: var(--muted); font-size: 0.7rem; }

/* Recent files */
.recent-list { padding: 0.8rem 1.2rem; display: flex; flex-direction: column; gap: 0.6rem; }
.recent-item {
  display: flex; align-items: center; justify-content: space-between;
  gap: 1rem; flex-wrap: wrap;
  padding: 0.6rem 0.8rem; border-radius: 8px;
  background: var(--bg-hover); border: 1px solid var(--border);
}
.recent-name { font-size: 0.8rem; word-break: break-all; }
.recent-meta { display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap; }
.meta-text   { font-size: 0.75rem; color: var(--muted); }

.tag { padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.72rem; font-weight: 700; }
.tag-ok   { background: #39d98a22; color: var(--ok);   border: 1px solid #39d98a44; }
.tag-warn { background: #ffb34722; color: var(--warn); border: 1px solid #ffb34744; }

.error-bar {
  background: #ff4d4d15; border: 1px solid #ff4d4d44;
  color: var(--danger); border-radius: 8px; padding: 0.7rem 1rem; font-size: 0.85rem;
}
</style>