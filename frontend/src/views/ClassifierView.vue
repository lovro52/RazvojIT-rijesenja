<template>
  <div class="cls-view">

    <div class="page-header">
      <h1>Klasifikator toka</h1>
      <p class="subtitle">
        Fine-tunani modeli klasificiraju pojedinačni mrežni tok — tip napada i razina rizika.
        Odvojeno od RAG sloja, koji piše izvještaj iz više dohvaćenih dokaza.
      </p>
    </div>

    <!-- Modeli -->
    <div class="models-row">
      <div
        v-for="m in models" :key="m.id"
        class="model-card"
        :class="{ selected: selected === m.id, missing: !m.installed }"
        @click="m.installed && (selected = m.id)"
      >
        <div class="mc-top">
          <span class="mc-name">{{ m.name }}</span>
          <span class="mc-dot" :class="m.installed ? 'ok' : 'off'"></span>
        </div>
        <div class="mc-size">{{ m.size }}</div>
        <div class="mc-desc">{{ m.description }}</div>
        <div v-if="m.accuracy" class="mc-stats">
          <span>{{ m.accuracy }}%</span>
          <span class="sep">·</span>
          <span :class="m.latency_ms < 10000 ? 'fast' : 'slow'">
            {{ (m.latency_ms / 1000).toFixed(1) }}s
          </span>
        </div>
        <div v-if="!m.installed" class="mc-missing">nije u Ollami</div>
      </div>
    </div>

    <div v-if="noneInstalled" class="warn-bar">
      ⚠ Nijedan fine-tunani model nije registriran u Ollami.
      Vidi <code>docs/OLLAMA_SETUP.md</code> za postupak.
    </div>

    <!-- Kontrole -->
    <div class="controls">
      <select v-model="file" class="sel grow">
        <option value="">Odaberi uploadanu datoteku…</option>
        <option v-for="f in files" :key="f.filename" :value="f.filename">
          {{ f.filename }}
        </option>
      </select>
      <select v-model.number="limit" class="sel">
        <option :value="5">5 tokova</option>
        <option :value="10">10 tokova</option>
        <option :value="20">20 tokova</option>
        <option :value="50">50 tokova</option>
      </select>
      <button class="btn" :disabled="!file || loading || noneInstalled" @click="run">
        <span v-if="loading" class="spin"></span>
        {{ loading ? 'Klasificiram…' : 'Klasificiraj' }}
      </button>
    </div>

    <div v-if="loading" class="hint">
      Inferenca traje sekunde po toku — {{ limit }} tokova je otprilike
      {{ Math.ceil(limit * (selectedModel?.latency_ms ?? 3000) / 1000 / 60) }} min.
    </div>
    <div v-if="error" class="err-bar">⚠ {{ error }}</div>

    <!-- Rezultat -->
    <template v-if="result">
      <div class="summary">
        <div class="sm">
          <span class="sm-val">{{ result.classified }}</span>
          <span class="sm-lbl">klasificirano</span>
        </div>
        <div class="sm">
          <span class="sm-val">{{ (result.avg_inference_ms / 1000).toFixed(1) }}s</span>
          <span class="sm-lbl">prosječno po toku</span>
        </div>
        <div class="sm" v-if="result.accuracy_vs_ground_truth != null">
          <span class="sm-val" :class="accClass">{{ result.accuracy_vs_ground_truth }}%</span>
          <span class="sm-lbl">vs stvarna oznaka</span>
        </div>
        <div class="sm" v-if="result.failed">
          <span class="sm-val warn">{{ result.failed }}</span>
          <span class="sm-lbl">neuspjelo</span>
        </div>
      </div>

      <div class="dist-card">
        <div class="card-title">Raspodjela detekcija</div>
        <div class="chips">
          <span
            v-for="(n, k) in result.attack_distribution" :key="k"
            class="chip" :class="k === 'BENIGN' ? 'ok' : 'danger'"
          >{{ k }} <b>{{ n }}</b></span>
        </div>
      </div>

      <div class="table-card">
        <div class="card-title">
          Tokovi
          <span class="note">stvarna oznaka služi samo za usporedbu — model je ne vidi</span>
        </div>
        <div class="twrap">
          <table>
            <thead>
              <tr>
                <th>Tok</th>
                <th>Port</th>
                <th>Detektirano</th>
                <th>Rizik</th>
                <th>Stvarno</th>
                <th>ms</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in result.results" :key="i">
                <td class="msg">{{ shorten(r.message) }}</td>
                <td>{{ r.dst_port ?? '—' }}</td>
                <td>
                  <span class="chip sm" :class="r.attack_type === 'BENIGN' ? 'ok' : 'danger'">
                    {{ r.attack_type }}
                  </span>
                </td>
                <td :class="riskCls(r.risk_level)">{{ r.risk_level }}</td>
                <td>
                  <span v-if="r.ground_truth" :class="matches(r) ? 'hit' : 'miss'">
                    {{ r.ground_truth }}
                  </span>
                  <span v-else class="muted">—</span>
                </td>
                <td class="muted">{{ Math.round(r.inference_ms) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const models   = ref([])
const files    = ref([])
const selected = ref('')
const file     = ref('')
const limit    = ref(10)
const loading  = ref(false)
const error    = ref(null)
const result   = ref(null)

const noneInstalled = computed(() =>
  models.value.length > 0 && !models.value.some(m => m.installed)
)
const selectedModel = computed(() =>
  models.value.find(m => m.id === selected.value)
)
const accClass = computed(() => {
  const a = result.value?.accuracy_vs_ground_truth
  if (a == null) return ''
  return a >= 90 ? 'good' : a >= 70 ? 'warn' : 'bad'
})

async function load() {
  try {
    const [mr, fr] = await Promise.all([
      axios.get('/logs/classifier/models'),
      axios.get('/logs/files'),
    ])
    models.value = mr.data.models
    files.value  = fr.data.files ?? []
    const first  = models.value.find(m => m.installed)
    selected.value = first ? first.id : mr.data.default
  } catch (e) {
    error.value = 'Backend nije dostupan.'
  }
}

async function run() {
  loading.value = true
  error.value   = null
  result.value  = null
  try {
    const { data } = await axios.post('/logs/classifier/classify', null, {
      params: { filename: file.value, limit: limit.value, model: selected.value },
    })
    result.value = data
  } catch (e) {
    error.value = e.response?.data?.detail ?? 'Klasifikacija nije uspjela.'
  } finally {
    loading.value = false
  }
}

function shorten(m) {
  if (!m) return '—'
  return m.length > 60 ? m.slice(0, 60) + '…' : m
}

function riskCls(r) {
  return r === 'HIGH' ? 'bad' : r === 'MEDIUM' ? 'warn' : r === 'LOW' ? 'good' : 'muted'
}

/** CICIDS koristi granularnije oznake od modela (DoS Hulk → DoS). */
function matches(r) {
  const gt = String(r.ground_truth || '').toLowerCase()
  const pr = String(r.attack_type  || '').toLowerCase()
  if (gt === pr) return true
  if (gt.startsWith('dos') || gt === 'heartbleed') return pr === 'dos'
  if (gt.includes('web attack')) return pr === 'webattack'
  return gt.replace(/-/g, '') === pr.replace(/-/g, '')
}

onMounted(load)
</script>

<style scoped>
.cls-view { display: flex; flex-direction: column; gap: 1.3rem; }
.page-header h1 {
  font-family: var(--font-head); font-size: 1.8rem;
  font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; line-height: 1.6; }

.models-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 0.8rem; }
.model-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: 1rem 1.1rem; cursor: pointer;
  transition: all .18s; display: flex; flex-direction: column; gap: .3rem;
}
.model-card:hover:not(.missing) { border-color: var(--accent); }
.model-card.selected { border-color: var(--accent); background: var(--accent-dim); }
.model-card.missing  { opacity: .5; cursor: not-allowed; }
.mc-top  { display: flex; align-items: center; justify-content: space-between; }
.mc-name { font-size: .88rem; font-weight: 700; }
.mc-dot  { width: 8px; height: 8px; border-radius: 50%; }
.mc-dot.ok  { background: var(--ok); }
.mc-dot.off { background: var(--muted); }
.mc-size { font-size: .72rem; color: var(--accent); }
.mc-desc { font-size: .76rem; color: var(--muted); line-height: 1.5; }
.mc-stats { font-size: .78rem; display: flex; gap: .4rem; margin-top: .2rem; }
.mc-stats .fast { color: var(--ok); }
.mc-stats .slow { color: var(--warn); }
.sep { color: var(--border); }
.mc-missing { font-size: .7rem; color: var(--warn); margin-top: .2rem; }

.controls { display: flex; gap: .6rem; flex-wrap: wrap; }
.sel {
  background: var(--bg-hover); border: 1px solid var(--border); color: var(--text);
  border-radius: 7px; padding: .45rem .7rem; font-size: .82rem; outline: none; cursor: pointer;
}
.sel.grow { flex: 1; min-width: 220px; }
.btn {
  display: flex; align-items: center; gap: .5rem;
  background: var(--accent); color: #000; border: none; border-radius: 7px;
  padding: .5rem 1.3rem; font-weight: 700; font-size: .82rem; cursor: pointer;
  transition: filter .2s; white-space: nowrap;
}
.btn:hover:not(:disabled) { filter: brightness(1.15); }
.btn:disabled { opacity: .4; cursor: not-allowed; }
.spin {
  width: 11px; height: 11px; border: 2px solid #00000044; border-top-color: #000;
  border-radius: 50%; animation: sp .6s linear infinite; display: inline-block;
}
@keyframes sp { to { transform: rotate(360deg); } }

.hint     { font-size: .78rem; color: var(--muted); }
.warn-bar { background: #ffb34715; border: 1px solid #ffb34744; color: var(--warn);
            border-radius: 8px; padding: .6rem 1rem; font-size: .82rem; }
.warn-bar code { background: var(--bg-hover); padding: .1rem .35rem; border-radius: 3px; }
.err-bar  { background: #ff4d4d15; border: 1px solid #ff4d4d44; color: var(--danger);
            border-radius: 8px; padding: .7rem 1rem; font-size: .85rem; }

.summary { display: flex; gap: 1.5rem; flex-wrap: wrap;
           background: var(--bg-card); border: 1px solid var(--border);
           border-radius: 12px; padding: 1rem 1.3rem; }
.sm      { display: flex; flex-direction: column; gap: .15rem; }
.sm-val  { font-family: var(--font-head); font-size: 1.4rem; font-weight: 800; }
.sm-lbl  { font-size: .72rem; color: var(--muted); }
.sm-val.good { color: var(--ok); } .sm-val.warn { color: var(--warn); }
.sm-val.bad  { color: var(--danger); }

.dist-card, .table-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; overflow: hidden;
}
.card-title {
  padding: .7rem 1.1rem; border-bottom: 1px solid var(--border);
  font-size: .82rem; font-weight: 600; display: flex; gap: .6rem;
  align-items: baseline; flex-wrap: wrap;
}
.note { font-size: .7rem; color: var(--muted); font-weight: 400; font-style: italic; }
.chips { padding: .8rem 1.1rem; display: flex; flex-wrap: wrap; gap: .4rem; }
.chip  { padding: .15rem .6rem; border-radius: 5px; font-size: .75rem; }
.chip.sm { font-size: .7rem; font-weight: 700; }
.chip.ok     { background: #39d98a22; color: var(--ok);     border: 1px solid #39d98a44; }
.chip.danger { background: #ff4d4d18; color: var(--danger); border: 1px solid #ff4d4d44; }

.twrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .78rem; }
th { text-align: left; padding: .5rem .8rem; background: var(--bg-hover);
     color: var(--muted); font-size: .72rem; border-bottom: 1px solid var(--border); white-space: nowrap; }
td { padding: .45rem .8rem; border-bottom: 1px solid var(--border); white-space: nowrap; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg-hover); }
.msg   { font-size: .73rem; color: var(--muted); max-width: 320px; }
.muted { color: var(--muted); }
.good  { color: var(--ok); } .warn { color: var(--warn); } .bad { color: var(--danger); }
.hit   { color: var(--ok); }
.miss  { color: var(--danger); text-decoration: underline; text-decoration-style: dotted; }
</style>