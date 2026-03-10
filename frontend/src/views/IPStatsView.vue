<template>
  <div class="ip-view">

    <div class="page-header">
      <h1>IP Statistike</h1>
      <p class="subtitle">Detaljne statistike po izvornim IP adresama.</p>
    </div>

    <!-- IP list + detail layout -->
    <div class="layout">

      <!-- Left: IP list -->
      <div class="ip-list-panel">
        <div class="panel-header">Izvorne IP adrese</div>
        <div v-if="loadingIps" class="loading">Učitavanje...</div>
        <div v-else class="ip-list">
          <div
            v-for="item in ips"
            :key="item.ip"
            class="ip-item"
            :class="{ active: selectedIp === item.ip }"
            @click="selectIp(item.ip)"
          >
            <span class="ip-addr">{{ item.ip }}</span>
            <span class="ip-count">{{ item.count }}</span>
          </div>
          <div v-if="ips.length === 0" class="empty-list">
            Nema podataka. Uploadaj i indeksiraj logove.
          </div>
        </div>
      </div>

      <!-- Right: IP detail -->
      <div class="ip-detail-panel">

        <div v-if="!selectedIp" class="no-selection">
          <span class="no-sel-icon">⊙</span>
          <p>Odaberi IP adresu s lijeve strane</p>
        </div>

        <div v-else-if="loadingDetail" class="loading">Učitavanje detalja...</div>

        <template v-else-if="detail">

          <!-- IP header -->
          <div class="detail-header">
            <span class="detail-ip">{{ detail.ip }}</span>
            <div class="detail-badges">
              <span class="badge accent">↑ {{ detail.as_source }} kao izvor</span>
              <span class="badge muted">↓ {{ detail.as_destination }} kao odredište</span>
              <span class="badge warn">{{ formatBytes(detail.total_bytes) }} poslano</span>
            </div>
          </div>

          <div class="detail-grid">

            <!-- Actions -->
            <div class="detail-card">
              <div class="detail-card-title"><span class="warn">⚑</span> Akcije</div>
              <div class="bar-list">
                <div v-for="a in detail.actions" :key="a.action" class="bar-item">
                  <span class="bar-label">{{ a.action }}</span>
                  <div class="bar-track">
                    <div
                      class="bar-fill"
                      :class="actionFill(a.action)"
                      :style="{ width: pct(a.count, maxAction) + '%' }"
                    ></div>
                  </div>
                  <span class="bar-count">{{ a.count }}</span>
                </div>
              </div>
            </div>

            <!-- Target ports -->
            <div class="detail-card">
              <div class="detail-card-title"><span class="danger">⊙</span> Ciljani portovi</div>
              <div class="bar-list">
                <div v-for="p in detail.dst_ports" :key="p.dst_port" class="bar-item">
                  <span class="bar-label">
                    {{ p.dst_port }}
                    <span class="port-hint">{{ portHint(p.dst_port) }}</span>
                  </span>
                  <div class="bar-track">
                    <div
                      class="bar-fill danger-fill"
                      :style="{ width: pct(p.count, detail.dst_ports[0]?.count) + '%' }"
                    ></div>
                  </div>
                  <span class="bar-count">{{ p.count }}</span>
                </div>
              </div>
            </div>

            <!-- Contacted IPs -->
            <div class="detail-card">
              <div class="detail-card-title"><span class="accent">◈</span> Kontaktirane IP adrese</div>
              <div class="contacted-list">
                <div v-for="c in detail.contacted_ips" :key="c.dst_ip" class="contacted-item">
                  <span class="contacted-ip" @click="selectIp(c.dst_ip)">{{ c.dst_ip }}</span>
                  <span class="contacted-count">{{ c.count }}×</span>
                </div>
              </div>
            </div>

            <!-- Risk assessment -->
            <div class="detail-card">
              <div class="detail-card-title"><span class="ok">⬡</span> Procjena rizika</div>
              <div class="risk-assess">
                <div class="risk-row" v-if="hasPsh">
                  <span class="risk-dot danger"></span>
                  <span>PSH paketi detektirani — moguće exfiltriranje podataka</span>
                </div>
                <div class="risk-row" v-if="targetsSSH">
                  <span class="risk-dot danger"></span>
                  <span>Konekcije na port 22 (SSH) — mogući brute-force</span>
                </div>
                <div class="risk-row" v-if="targetsRDP">
                  <span class="risk-dot danger"></span>
                  <span>Konekcije na port 3389 (RDP) — visoki rizik</span>
                </div>
                <div class="risk-row" v-if="manySynPorts">
                  <span class="risk-dot warn"></span>
                  <span>SYN paketi na više portova — mogući port scan</span>
                </div>
                <div class="risk-row" v-if="!hasPsh && !targetsSSH && !targetsRDP && !manySynPorts">
                  <span class="risk-dot ok"></span>
                  <span>Nije detektirana sumnjiva aktivnost</span>
                </div>
              </div>
            </div>

          </div>

          <!-- Log records table -->
          <div class="detail-card full-width">
            <div class="detail-card-title">
              <span class="muted">≡</span> Svi logovi
              <span class="count-badge">{{ detail.records.length }}</span>
            </div>
            <div class="table-wrap">
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
                  <tr v-for="(r, i) in detail.records" :key="i">
                    <td>{{ r.timestamp ?? '—' }}</td>
                    <td class="ip-cell" :class="{ highlight: r.src_ip === detail.ip }">{{ r.src_ip ?? '—' }}</td>
                    <td class="ip-cell" :class="{ highlight: r.dst_ip === detail.ip }">{{ r.dst_ip ?? '—' }}</td>
                    <td>{{ r.src_port ?? '—' }}</td>
                    <td>{{ r.dst_port ?? '—' }}</td>
                    <td><span class="proto-chip">{{ r.protocol }}</span></td>
                    <td>{{ r.bytes ?? '—' }}</td>
                    <td>
                      <span class="action-chip" :class="actionChip(r.action)">{{ r.action }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

        </template>

      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const ips           = ref([])
const selectedIp    = ref(null)
const detail        = ref(null)
const loadingIps    = ref(false)
const loadingDetail = ref(false)

const maxAction = computed(() =>
  detail.value ? Math.max(...detail.value.actions.map(a => a.count), 1) : 1
)

const hasPsh      = computed(() => detail.value?.actions.some(a => a.action === 'PSH'))
const targetsSSH  = computed(() => detail.value?.dst_ports.some(p => p.dst_port === 22))
const targetsRDP  = computed(() => detail.value?.dst_ports.some(p => p.dst_port === 3389))
const manySynPorts = computed(() => {
  if (!detail.value) return false
  const syn = detail.value.actions.find(a => a.action === 'SYN')
  return syn && detail.value.dst_ports.length >= 3
})

async function loadIps() {
  loadingIps.value = true
  try {
    const { data } = await axios.get('/logs/ips')
    ips.value = data.ips
  } catch (e) {
    console.error(e)
  } finally {
    loadingIps.value = false
  }
}

async function selectIp(ip) {
  selectedIp.value    = ip
  detail.value        = null
  loadingDetail.value = true
  try {
    const { data } = await axios.get(`/logs/ips/${ip}`)
    detail.value = data
  } catch (e) {
    console.error(e)
  } finally {
    loadingDetail.value = false
  }
}

function pct(val, max) {
  return max ? Math.round((val / max) * 100) : 0
}

function actionFill(action) {
  if (action === 'PSH') return 'warn-fill'
  if (action === 'SYN') return 'accent-fill'
  if (action === 'ACK') return 'ok-fill'
  return 'muted-fill'
}

function actionChip(action) {
  if (action === 'PSH') return 'chip-warn'
  if (action === 'SYN') return 'chip-accent'
  if (action === 'ACK') return 'chip-ok'
  return ''
}

function portHint(port) {
  const h = { 22: 'SSH', 23: 'Telnet', 80: 'HTTP', 443: 'HTTPS', 3306: 'MySQL', 3389: 'RDP', 8080: 'HTTP-alt' }
  return h[port] ? `(${h[port]})` : ''
}

function formatBytes(b) {
  if (!b) return '0 B'
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 / 1024).toFixed(1)} MB`
}

onMounted(loadIps)
</script>

<style scoped>
.ip-view { display: flex; flex-direction: column; gap: 1.5rem; }

.page-header h1 {
  font-family: var(--font-head); font-size: 1.8rem;
  font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }

/* Layout */
.layout { display: grid; grid-template-columns: 220px 1fr; gap: 1rem; align-items: start; }
@media (max-width: 700px) { .layout { grid-template-columns: 1fr; } }

/* IP list panel */
.ip-list-panel {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; overflow: hidden; position: sticky; top: 70px;
}
.panel-header {
  padding: 0.7rem 1rem; border-bottom: 1px solid var(--border);
  font-size: 0.75rem; letter-spacing: 0.08em; color: var(--muted); font-weight: 600;
}
.ip-list { display: flex; flex-direction: column; }
.ip-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.6rem 1rem; cursor: pointer; transition: all 0.15s;
  border-bottom: 1px solid var(--border); font-size: 0.82rem;
}
.ip-item:last-child { border-bottom: none; }
.ip-item:hover { background: var(--bg-hover); }
.ip-item.active { background: var(--accent-dim); color: var(--accent); border-left: 2px solid var(--accent); }
.ip-addr { font-size: 0.8rem; }
.ip-count {
  background: var(--bg-hover); border-radius: 4px;
  padding: 0.1rem 0.4rem; font-size: 0.7rem; color: var(--muted);
}
.ip-item.active .ip-count { background: var(--accent); color: #000; }
.empty-list { padding: 1.2rem 1rem; font-size: 0.8rem; color: var(--muted); }
.loading { padding: 1rem; font-size: 0.82rem; color: var(--muted); }

/* Detail panel */
.ip-detail-panel { display: flex; flex-direction: column; gap: 1rem; }

.no-selection {
  background: var(--bg-card); border: 1px dashed var(--border);
  border-radius: 12px; padding: 3rem; text-align: center;
  color: var(--muted); display: flex; flex-direction: column; align-items: center; gap: 0.8rem;
}
.no-sel-icon { font-size: 2rem; color: var(--border); }

/* Detail header */
.detail-header {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.2rem 1.4rem;
  display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
}
.detail-ip {
  font-family: var(--font-head); font-size: 1.4rem;
  font-weight: 800; color: var(--accent);
}
.detail-badges { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.badge {
  padding: 0.2rem 0.7rem; border-radius: 6px; font-size: 0.75rem; font-weight: 600;
}
.badge.accent { background: var(--accent-dim); color: var(--accent); border: 1px solid #00e5ff33; }
.badge.muted  { background: var(--bg-hover);   color: var(--muted);  border: 1px solid var(--border); }
.badge.warn   { background: #ffb34722;          color: var(--warn);   border: 1px solid #ffb34744; }

/* Detail grid */
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 800px) { .detail-grid { grid-template-columns: 1fr; } }

.detail-card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden;
}
.full-width { grid-column: 1 / -1; }

.detail-card-title {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.7rem 1.1rem; border-bottom: 1px solid var(--border);
  font-size: 0.8rem; font-weight: 600; letter-spacing: 0.06em;
}
.count-badge {
  margin-left: auto; background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: 4px; padding: 0.1rem 0.5rem; font-size: 0.72rem; color: var(--muted);
}
.warn   { color: var(--warn); }
.danger { color: var(--danger); }
.accent { color: var(--accent); }
.ok     { color: var(--ok); }
.muted  { color: var(--muted); }

/* Bars */
.bar-list { padding: 0.7rem 1.1rem; display: flex; flex-direction: column; gap: 0.55rem; }
.bar-item { display: flex; align-items: center; gap: 0.5rem; }
.bar-label { width: 80px; font-size: 0.76rem; flex-shrink: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.port-hint { font-size: 0.68rem; color: var(--muted); }
.bar-track { flex: 1; height: 5px; background: var(--bg-hover); border-radius: 3px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease; }
.accent-fill { background: var(--accent); }
.warn-fill   { background: var(--warn); }
.ok-fill     { background: var(--ok); }
.danger-fill { background: var(--danger); }
.muted-fill  { background: var(--muted); }
.bar-count { font-size: 0.72rem; color: var(--muted); width: 22px; text-align: right; flex-shrink: 0; }

/* Contacted IPs */
.contacted-list { padding: 0.7rem 1.1rem; display: flex; flex-direction: column; gap: 0.4rem; }
.contacted-item { display: flex; align-items: center; justify-content: space-between; }
.contacted-ip {
  font-size: 0.8rem; color: var(--accent); cursor: pointer;
  text-decoration: underline; text-decoration-color: transparent;
  transition: text-decoration-color 0.2s;
}
.contacted-ip:hover { text-decoration-color: var(--accent); }
.contacted-count { font-size: 0.75rem; color: var(--muted); }

/* Risk assessment */
.risk-assess { padding: 0.7rem 1.1rem; display: flex; flex-direction: column; gap: 0.6rem; }
.risk-row { display: flex; align-items: flex-start; gap: 0.6rem; font-size: 0.82rem; line-height: 1.5; }
.risk-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 5px;
}
.risk-dot.danger { background: var(--danger); }
.risk-dot.warn   { background: var(--warn); }
.risk-dot.ok     { background: var(--ok); }

/* Table */
.table-wrap { overflow-x: auto; padding: 0 0 0.5rem; }
table { width: 100%; border-collapse: collapse; font-size: 0.76rem; }
th {
  text-align: left; color: var(--muted); padding: 0.45rem 0.8rem;
  border-bottom: 1px solid var(--border); white-space: nowrap; letter-spacing: 0.04em;
  background: var(--bg-card);
}
td { padding: 0.4rem 0.8rem; border-bottom: 1px solid var(--border); white-space: nowrap; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg-hover); }
.ip-cell { color: var(--muted); }
.ip-cell.highlight { color: var(--accent); font-weight: 500; }

.proto-chip {
  background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: 4px; padding: 0.1rem 0.4rem; font-size: 0.7rem;
}
.action-chip { border-radius: 4px; padding: 0.1rem 0.5rem; font-size: 0.7rem; font-weight: 700; }
.chip-warn   { background: #ffb34722; color: var(--warn);   border: 1px solid #ffb34744; }
.chip-accent { background: #00e5ff22; color: var(--accent); border: 1px solid #00e5ff44; }
.chip-ok     { background: #39d98a22; color: var(--ok);     border: 1px solid #39d98a44; }
</style>