<template>
  <div class="query-view">

    <div class="page-header">
      <h1>Analiza logova</h1>
      <p class="subtitle">Postavi pitanje o mreži — sustav rangira agregirane incidente i generira sigurnosnu analizu.</p>
    </div>

    <!-- Suggested queries -->
    <div class="suggestions">
      <div class="suggestions-label">Brza pitanja:</div>
      <div class="suggestion-groups">
        <div v-for="group in suggestionGroups" :key="group.label" class="suggestion-group">
          <span class="group-label" :class="group.color">{{ group.icon }} {{ group.label }}</span>
          <div class="group-pills">
            <button
              v-for="s in group.items"
              :key="s.query"
              class="pill"
              :class="{ active: query === s.query }"
              @click="selectSuggestion(s.query)"
            >
              {{ s.text }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Search bar -->
    <div class="search-bar">
      <span class="search-icon">⌕</span>
      <input
        v-model="query"
        type="text"
        placeholder="Napiši pitanje ili odaberi jedno gore..."
        @keydown.enter="runQuery"
      />
      <select v-model="selectedSource" class="model-select" title="Odaberi indeksiranu datoteku">
        <option value="" disabled>Odaberi datoteku</option>
        <option v-for="file in indexedFiles" :key="file.filename" :value="file.filename">
          {{ file.filename }}
        </option>
      </select>
      <select v-model="detectionMode" class="mode-select" title="Način detekcije">
        <option value="auto">Automatski</option>
        <option value="flow">Mrežni tokovi</option>
      </select>
      <select v-model="selectedModel" class="model-select" title="Odaberi model">
        <option value="">Zadani model</option>
        <option v-for="m in ragModels" :key="m.id" :value="m.id">{{ m.name }}</option>
      </select>
      <select v-model="topK" class="topk-select">
        <option :value="3">top 3</option>
        <option :value="5">top 5</option>
        <option :value="10">top 10</option>
      </select>
      <button class="btn-primary" :disabled="!query.trim() || !selectedSource || loading" @click="runQuery">
        <span v-if="loading" class="spinner"></span>
        {{ loading ? 'Analiziram...' : 'Analiziraj' }}
      </button>
    </div>

    <!-- Inference speed bar -->
    <div v-if="result" class="inference-bar">
      <span class="inf-item">
        <span class="inf-label">Model</span>
        <span class="inf-value accent">{{ result.report.model_used ?? selectedModel ?? 'llama3.1:8b' }}</span>
      </span>
      <span class="inf-sep">·</span>
      <span class="inf-item">
        <span class="inf-label">Mod</span>
        <span class="inf-value">Mrežni tokovi</span>
      </span>
      <span class="inf-sep">·</span>
      <span class="inf-item">
        <span class="inf-label">Inference</span>
        <span class="inf-value" :class="speedClass">{{ result.report.inference_ms }} ms</span>
      </span>
      <span class="inf-sep">·</span>
      <span class="inf-item">
        <span class="inf-label">Dokaza</span>
        <span class="inf-value">{{ result.evidence.length }}</span>
      </span>
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
        <button class="btn-pdf" @click="exportPdf">
          ↓ Izvezi PDF
        </button>
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
          <div v-for="(ev, i) in result.report.evidence_highlights" :key="i" class="evidence-item">
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
          <div v-for="(rec, i) in result.evidence" :key="i" class="log-item">
            <div class="log-top">
              <span class="log-id">{{ rec.id }}</span>
              <span class="log-dist">rang-sličnost: {{ rec.similarity.toFixed(4) }}</span>
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
import { ref, computed, onMounted } from 'vue'
import api, { errorMessage } from '../services/api'
import { jsPDF } from 'jspdf'

const query          = ref('')
const topK           = ref(5)
const selectedModel  = ref('')
const detectionMode  = ref('auto')
const loading        = ref(false)
const error          = ref(null)
const result         = ref(null)
const models         = ref([])
const files          = ref([])
const selectedSource = ref('')
const indexedFiles   = computed(() => files.value.filter(file => file.indexed))
const ragModels      = computed(() => models.value.filter(model => model.type === 'rag'))

const speedClass = computed(() => {
  const ms = result.value?.report?.inference_ms
  if (!ms) return ''
  if (ms < 3000)  return 'speed-fast'
  if (ms < 8000)  return 'speed-medium'
  return 'speed-slow'
})

async function loadContext() {
  try {
    const [modelsResponse, filesResponse] = await Promise.all([
      api.get('/logs/models'),
      api.get('/logs/files'),
    ])
    models.value = modelsResponse.data.models
    files.value = filesResponse.data.files
    selectedSource.value = indexedFiles.value[0]?.filename ?? ''
  } catch (e) {
    error.value = errorMessage(e, 'Nije moguće učitati modele i datoteke.')
  }
}

const suggestionGroups = [
  {
    label: 'Opća sigurnost',
    icon:  '🛡️',
    color: 'color-ok',
    items: [
      { text: 'Je li mreža sigurna?',             query: 'Is there any suspicious or dangerous network activity?' },
      { text: 'Ima li neobičnog prometa?',         query: 'Are there any unusual or abnormal traffic patterns?' },
      { text: 'Koji uređaji šalju najviše podataka?', query: 'Which hosts are sending the most data?' },
    ],
  },
  {
    label: 'Upadi i napadi',
    icon:  '⚠️',
    color: 'color-warn',
    items: [
      { text: 'Pokušava li netko provaliti?',      query: 'Is there any brute force or login attack attempt?' },
      { text: 'Ima li skeniranja portova?',         query: 'Is anyone scanning ports or probing the network?' },
      { text: 'Ima li DDoS napada?',                query: 'Is there a denial of service or flood attack?' },
    ],
  },
  {
    label: 'Sumnjive aktivnosti',
    icon:  '🔍',
    color: 'color-danger',
    items: [
      { text: 'Veliki odlazni promet?',              query: 'Are there unusually large outbound traffic windows?' },
      { text: 'Učestale SSH ili FTP veze?',          query: 'Are there repeated connections to SSH or FTP services?' },
      { text: 'Najaktivnije izvorne adrese?',        query: 'Which source addresses have the most repeated connections?' },
    ],
  },
]

function selectSuggestion(q) {
  query.value = q
  runQuery()
}

const riskClass = computed(() => {
  const r = result.value?.report?.risk_level
  if (r === 'HIGH')   return 'risk-high'
  if (r === 'MEDIUM') return 'risk-medium'
  if (r === 'LOW')    return 'risk-low'
  return 'risk-unknown'
})

async function runQuery() {
  if (!query.value.trim() || !selectedSource.value) return
  loading.value = true
  error.value   = null
  result.value  = null
  try {
    const params = {
      q: query.value,
      top_k: topK.value,
      mode: detectionMode.value,
      source_file: selectedSource.value,
    }
    if (selectedModel.value) params.model = selectedModel.value
    const { data } = await api.get('/logs/query/rag_local_mode', { params, timeout: 0 })
    result.value = data
  } catch (e) {
    error.value = errorMessage(e, 'Analiza nije uspjela.')
  } finally {
    loading.value = false
  }
}

onMounted(loadContext)

function exportPdf() {
  const doc    = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  const report = result.value.report
  const W      = 210
  const margin = 18
  const maxW   = W - margin * 2
  let y        = 20

  const riskColors = {
    HIGH:   [255, 77,  77],
    MEDIUM: [255, 179, 71],
    LOW:    [57,  217, 138],
  }
  const riskColor = riskColors[report.risk_level] ?? [100, 116, 139]

  // ── Header bar ──
  doc.setFillColor(...riskColor)
  doc.rect(0, 0, W, 14, 'F')
  doc.setTextColor(0, 0, 0)
  doc.setFontSize(9)
  doc.setFont('helvetica', 'bold')
  doc.text('NETLOGRAG — SIGURNOSNI IZVJEŠTAJ', margin, 9)
  doc.text(new Date().toLocaleString(), W - margin, 9, { align: 'right' })

  y = 24

  // ── Title ──
  doc.setTextColor(20, 20, 20)
  doc.setFontSize(18)
  doc.setFont('helvetica', 'bold')
  doc.text('Sigurnosni izvještaj', margin, y)
  y += 8

  // ── Query ──
  doc.setFontSize(9)
  doc.setFont('helvetica', 'normal')
  doc.setTextColor(100, 116, 139)
  doc.text(`Upit: ${result.value.query}`, margin, y)
  y += 10

  // ── Risk level box ──
  doc.setFillColor(...riskColor.map(c => Math.min(255, c + 160)))
  doc.roundedRect(margin, y, maxW, 18, 3, 3, 'F')
  doc.setFillColor(...riskColor)
  doc.roundedRect(margin, y, 32, 18, 3, 3, 'F')
  doc.setTextColor(0, 0, 0)
  doc.setFontSize(8)
  doc.setFont('helvetica', 'bold')
  doc.text('RAZINA RIZIKA', margin + 2, y + 6)
  doc.setFontSize(11)
  doc.text(report.risk_level ?? '—', margin + 2, y + 14)
  doc.setTextColor(30, 30, 30)
  doc.setFontSize(9)
  doc.setFont('helvetica', 'normal')
  const summaryLines = doc.splitTextToSize(report.summary ?? '', maxW - 38)
  doc.text(summaryLines, margin + 36, y + 7)
  y += 26

  // ── Section helper ──
  function section(title, items, color) {
    doc.setFillColor(...color)
    doc.rect(margin, y, 3, items.length * 7 + 10, 'F')
    doc.setTextColor(30, 30, 30)
    doc.setFontSize(10)
    doc.setFont('helvetica', 'bold')
    doc.text(title, margin + 6, y + 6)
    y += 11
    doc.setFontSize(8.5)
    doc.setFont('helvetica', 'normal')
    doc.setTextColor(50, 50, 50)
    items.forEach(item => {
      const lines = doc.splitTextToSize(`• ${item}`, maxW - 8)
      doc.text(lines, margin + 6, y)
      y += lines.length * 5.5
    })
    y += 6
  }

  section('Ključni indikatori',    report.key_indicators      ?? [], riskColor)
  section('Preporučene akcije',    report.recommended_actions ?? [], [57, 217, 138])

  // ── Evidence highlights ──
  if (report.evidence_highlights?.length) {
    doc.setFillColor(0, 229, 255)
    doc.rect(margin, y, 3, report.evidence_highlights.length * 10 + 10, 'F')
    doc.setTextColor(30, 30, 30)
    doc.setFontSize(10)
    doc.setFont('helvetica', 'bold')
    doc.text('Istaknuti dokazi', margin + 6, y + 6)
    y += 11
    report.evidence_highlights.forEach(ev => {
      doc.setFontSize(7.5)
      doc.setFont('helvetica', 'bold')
      doc.setTextColor(0, 150, 180)
      doc.text(ev.id ?? '', margin + 6, y)
      y += 4.5
      doc.setFont('helvetica', 'normal')
      doc.setTextColor(50, 50, 50)
      const lines = doc.splitTextToSize(ev.reason ?? '', maxW - 8)
      doc.text(lines, margin + 6, y)
      y += lines.length * 5 + 2
    })
    y += 4
  }

  // ── Evidence log records ──
  if (result.value.evidence?.length) {
    // New page if not enough space
    if (y > 240) { doc.addPage(); y = 20 }

    doc.setFillColor(30, 30, 40)
    doc.rect(margin, y, maxW, 8, 'F')
    doc.setTextColor(255, 255, 255)
    doc.setFontSize(9)
    doc.setFont('helvetica', 'bold')
    doc.text('Dohvaćeni log zapisi', margin + 3, y + 5.5)
    y += 11

    result.value.evidence.forEach((rec, idx) => {
      if (y > 270) { doc.addPage(); y = 20 }
      doc.setFillColor(idx % 2 === 0 ? 245 : 252, idx % 2 === 0 ? 245 : 252, idx % 2 === 0 ? 250 : 252)
      doc.rect(margin, y, maxW, 10, 'F')
      doc.setTextColor(0, 150, 180)
      doc.setFontSize(7)
      doc.setFont('helvetica', 'bold')
      doc.text(rec.id ?? '', margin + 2, y + 4)
      doc.setTextColor(60, 60, 60)
      doc.setFont('helvetica', 'normal')
      const docLines = doc.splitTextToSize(rec.document ?? '', maxW - 4)
      doc.text(docLines[0], margin + 2, y + 8)
      y += 12
    })
  }

  // ── Footer ──
  const pageCount = doc.internal.getNumberOfPages()
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i)
    doc.setFontSize(7)
    doc.setTextColor(150, 150, 150)
    doc.text(`NetlogRAG — Stranica ${i} od ${pageCount}`, W / 2, 290, { align: 'center' })
  }

  const filename = `security_report_${new Date().toISOString().slice(0, 10)}.pdf`
  doc.save(filename)
}
</script>

<style scoped>
.query-view { display: flex; flex-direction: column; gap: 1.5rem; }

.page-header h1 {
  font-family: var(--font-head); font-size: 1.8rem;
  font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }

/* Suggestions */
.suggestions {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1.1rem 1.3rem;
  display: flex; flex-direction: column; gap: 0.8rem;
}
.suggestions-label { font-size: 0.72rem; color: var(--muted); letter-spacing: 0.08em; font-weight: 600; }
.suggestion-groups { display: flex; flex-direction: column; gap: 0.8rem; }
.suggestion-group  { display: flex; align-items: flex-start; gap: 0.8rem; flex-wrap: wrap; }
.group-label {
  font-size: 0.72rem; font-weight: 700; letter-spacing: 0.04em;
  white-space: nowrap; padding-top: 0.35rem; min-width: 130px;
}
.color-ok     { color: var(--ok); }
.color-warn   { color: var(--warn); }
.color-danger { color: var(--danger); }
.group-pills  { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.pill {
  background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: 20px; padding: 0.3rem 0.9rem;
  font-size: 0.78rem; color: var(--text); cursor: pointer;
  transition: all 0.18s; white-space: nowrap;
}
.pill:hover  { border-color: var(--accent); color: var(--accent); background: var(--accent-dim); }
.pill.active { border-color: var(--accent); color: var(--accent); background: var(--accent-dim); }

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

.mode-select {
  background: var(--bg-hover); border: 1px solid var(--border);
  color: var(--text); border-radius: 6px; padding: 0.3rem 0.5rem;
  font-size: 0.78rem; outline: none; cursor: pointer;
}
.model-select {
  background: var(--bg-hover); border: 1px solid var(--border);
  color: var(--text); border-radius: 6px; padding: 0.3rem 0.6rem;
  font-size: 0.8rem; outline: none; cursor: pointer; max-width: 160px;
}
.topk-select {
  background: var(--bg-hover); border: 1px solid var(--border);
  color: var(--muted); border-radius: 6px; padding: 0.3rem 0.5rem;
  font-size: 0.8rem; outline: none; cursor: pointer;
}

/* Inference bar */
.inference-bar {
  display: flex; align-items: center; gap: 0.8rem; flex-wrap: wrap;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 8px; padding: 0.55rem 1rem; font-size: 0.78rem;
}
.inf-item  { display: flex; align-items: center; gap: 0.4rem; }
.inf-label { color: var(--muted); }
.inf-value { font-weight: 600; }
.inf-value.accent      { color: var(--accent); }
.inf-value.speed-fast  { color: var(--ok); }
.inf-value.speed-medium{ color: var(--warn); }
.inf-value.speed-slow  { color: var(--danger); }
.inf-sep   { color: var(--border); }

.btn-primary {
  display: flex; align-items: center; gap: 0.5rem;
  background: var(--accent); color: #000; border: none;
  border-radius: 7px; padding: 0.5rem 1.2rem;
  font-weight: 700; font-size: 0.82rem; letter-spacing: 0.05em;
  transition: all 0.2s; white-space: nowrap;
}
.btn-primary:hover:not(:disabled) { filter: brightness(1.15); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-pdf {
  background: #ffffff18; border: 1px solid #ffffff44;
  color: #fff; border-radius: 7px; padding: 0.45rem 1rem;
  font-size: 0.8rem; font-weight: 700; letter-spacing: 0.04em;
  cursor: pointer; transition: all 0.2s; white-space: nowrap;
  margin-left: auto; flex-shrink: 0;
}
.btn-pdf:hover { background: #ffffff30; }

.spinner {
  width: 11px; height: 11px; border: 2px solid #00000044;
  border-top-color: #000; border-radius: 50%;
  animation: spin 0.6s linear infinite; display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

.risk-banner {
  border-radius: 12px; padding: 1.2rem 1.5rem;
  display: flex; align-items: flex-start; gap: 2rem; flex-wrap: wrap;
}
.risk-high   { background: #ff4d4d18; border: 1px solid #ff4d4d55; }
.risk-medium { background: #ffb34718; border: 1px solid #ffb34755; }
.risk-low    { background: #39d98a18; border: 1px solid #39d98a55; }
.risk-unknown { background: #64748b18; border: 1px solid #64748b55; }

.risk-left { display: flex; flex-direction: column; gap: 0.2rem; flex-shrink: 0; }
.risk-label { font-size: 0.68rem; letter-spacing: 0.12em; color: var(--muted); }
.risk-value { font-family: var(--font-head); font-size: 1.6rem; font-weight: 800; letter-spacing: 0.05em; }
.risk-high   .risk-value { color: var(--danger); }
.risk-medium .risk-value { color: var(--warn); }
.risk-low    .risk-value { color: var(--ok); }
.risk-unknown .risk-value { color: var(--muted); }
.risk-summary { color: var(--text); font-size: 0.88rem; line-height: 1.7; padding-top: 0.2rem; flex: 1; }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
@media (max-width: 680px) { .grid-2 { grid-template-columns: 1fr; } }

.card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; overflow: hidden; }
.card-title {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.8rem 1.2rem; border-bottom: 1px solid var(--border);
  font-size: 0.82rem; letter-spacing: 0.06em; font-weight: 600;
}
.card-icon { font-size: 0.9rem; }
.card-icon.warn   { color: var(--warn); }
.card-icon.ok     { color: var(--ok); }
.card-icon.accent { color: var(--accent); }
.card-icon.muted  { color: var(--muted); }

.count-badge {
  margin-left: auto; background: var(--bg-hover); border: 1px solid var(--border);
  border-radius: 4px; padding: 0.1rem 0.5rem; font-size: 0.72rem; color: var(--muted);
}

.indicator-list { list-style: none; padding: 0.8rem 1.2rem; display: flex; flex-direction: column; gap: 0.5rem; }
.indicator-list li { display: flex; gap: 0.5rem; font-size: 0.83rem; line-height: 1.5; }
.bullet { color: var(--accent); flex-shrink: 0; }

.evidence-list { padding: 0.8rem 1.2rem; display: flex; flex-direction: column; gap: 0.6rem; }
.evidence-item { background: var(--bg-hover); border: 1px solid var(--border); border-radius: 8px; padding: 0.7rem 1rem; }
.ev-id { font-size: 0.75rem; color: var(--accent); margin-bottom: 0.2rem; }
.ev-reason { font-size: 0.82rem; color: var(--text); }

.log-list { padding: 0.8rem 1.2rem; display: flex; flex-direction: column; gap: 0.8rem; }
.log-item { border: 1px solid var(--border); border-radius: 8px; padding: 0.8rem 1rem; background: var(--bg-hover); }
.log-top { display: flex; justify-content: space-between; margin-bottom: 0.4rem; }
.log-id { font-size: 0.75rem; color: var(--accent); }
.log-dist { font-size: 0.72rem; color: var(--muted); }
.log-doc { font-size: 0.82rem; margin-bottom: 0.5rem; line-height: 1.5; }
.log-meta { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.meta-chip {
  display: flex; gap: 0.2rem; background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 4px; padding: 0.1rem 0.5rem; font-size: 0.7rem;
}
.meta-key { color: var(--muted); }
.meta-val { color: var(--text); }

.error-bar {
  background: #ff4d4d15; border: 1px solid #ff4d4d44;
  color: var(--danger); border-radius: 8px; padding: 0.7rem 1rem; font-size: 0.85rem;
}
</style>
