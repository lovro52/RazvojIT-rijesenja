<template>
  <div class="upload-view">

    <div class="page-header">
      <h1>Upload Logs</h1>
      <p class="subtitle">Upload a CSV network log file to index it for semantic search.</p>
    </div>

    <!-- Drop zone -->
    <div
      class="dropzone"
      :class="{ 'dragover': dragging, 'has-file': selectedFile }"
      @dragover.prevent="dragging = true"
      @dragleave="dragging = false"
      @drop.prevent="onDrop"
      @click="$refs.fileInput.click()"
    >
      <input ref="fileInput" type="file" accept=".csv" hidden @change="onFileChange" />
      <div v-if="!selectedFile" class="drop-content">
        <div class="drop-icon">⬆</div>
        <p class="drop-label">Drop CSV here or <span class="link">browse</span></p>
        <p class="drop-hint">Only .csv files are accepted</p>
      </div>
      <div v-else class="file-selected">
        <span class="file-icon">▣</span>
        <span class="file-name">{{ selectedFile.name }}</span>
        <span class="file-size">{{ (selectedFile.size / 1024).toFixed(1) }} KB</span>
        <button class="clear-btn" @click.stop="clearFile">✕</button>
      </div>
    </div>

    <!-- Upload button -->
    <div class="actions">
      <button class="btn-primary" :disabled="!selectedFile || uploading" @click="uploadFile">
        <span v-if="uploading" class="spinner"></span>
        {{ uploading ? 'Uploading...' : 'Upload' }}
      </button>
    </div>

    <!-- Upload result -->
    <div v-if="uploadResult" class="card result-card">
      <div class="card-header">
        <span class="tag tag-ok">✓ Uploaded</span>
        <span class="filename">{{ uploadResult.filename }}</span>
        <span class="meta">{{ uploadResult.rows }} rows · {{ uploadResult.columns.length }} columns</span>
      </div>

      <!-- Columns -->
      <div class="columns-row">
        <span v-for="col in uploadResult.columns" :key="col" class="col-chip">{{ col }}</span>
      </div>

      <!-- Preview table -->
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th v-for="col in uploadResult.columns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in uploadResult.preview" :key="i">
              <td v-for="col in uploadResult.columns" :key="col">{{ row[col] ?? '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Index button -->
      <div class="index-section">
        <button
          class="btn-primary"
          :disabled="indexing || indexed"
          @click="indexFile"
        >
          <span v-if="indexing" class="spinner"></span>
          {{ indexed ? '✓ Indexed' : indexing ? 'Indexing...' : 'Index into Vector Store' }}
        </button>
        <p v-if="indexed" class="index-ok">{{ indexResult.indexed_records }} records indexed successfully.</p>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="error-bar">⚠ {{ error }}</div>

  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const fileInput     = ref(null)
const selectedFile  = ref(null)
const dragging      = ref(false)
const uploading     = ref(false)
const indexing      = ref(false)
const indexed       = ref(false)
const uploadResult  = ref(null)
const indexResult   = ref(null)
const error         = ref(null)

function onFileChange(e) {
  const f = e.target.files[0]
  if (f) selectFile(f)
}

function onDrop(e) {
  dragging.value = false
  const f = e.dataTransfer.files[0]
  if (f) selectFile(f)
}

function selectFile(f) {
  if (!f.name.toLowerCase().endsWith('.csv')) {
    error.value = 'Only .csv files are accepted.'
    return
  }
  selectedFile.value = f
  uploadResult.value = null
  indexResult.value  = null
  indexed.value      = false
  error.value        = null
}

function clearFile() {
  selectedFile.value = null
  uploadResult.value = null
  indexed.value      = false
  error.value        = null
  if (fileInput.value) fileInput.value.value = ''
}

async function uploadFile() {
  if (!selectedFile.value) return
  uploading.value = true
  error.value     = null
  try {
    const fd = new FormData()
    fd.append('file', selectedFile.value)
    const { data } = await axios.post('/logs/upload', fd)
    uploadResult.value = data
  } catch (e) {
    error.value = e.response?.data?.detail ?? 'Upload failed.'
  } finally {
    uploading.value = false
  }
}

async function indexFile() {
  if (!uploadResult.value) return
  indexing.value = true
  error.value    = null
  try {
    const { data } = await axios.post(`/logs/index?filename=${uploadResult.value.filename}`)
    indexResult.value = data
    indexed.value     = true
  } catch (e) {
    error.value = e.response?.data?.detail ?? 'Indexing failed.'
  } finally {
    indexing.value = false
  }
}
</script>

<style scoped>
.upload-view { display: flex; flex-direction: column; gap: 1.5rem; }

.page-header h1 {
  font-family: var(--font-head);
  font-size: 1.8rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }

/* Dropzone */
.dropzone {
  border: 1.5px dashed var(--border);
  border-radius: 12px;
  padding: 3rem 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--bg-card);
}
.dropzone:hover, .dropzone.dragover {
  border-color: var(--accent);
  background: var(--accent-dim);
}
.dropzone.has-file {
  border-style: solid;
  border-color: var(--accent);
  padding: 1.2rem 2rem;
}
.drop-icon { font-size: 2rem; color: var(--muted); margin-bottom: 0.8rem; }
.drop-label { font-size: 0.95rem; margin-bottom: 0.3rem; }
.link { color: var(--accent); }
.drop-hint { color: var(--muted); font-size: 0.8rem; }

.file-selected {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  justify-content: center;
}
.file-icon { color: var(--accent); font-size: 1.2rem; }
.file-name { font-weight: 500; }
.file-size { color: var(--muted); font-size: 0.8rem; }
.clear-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 4px;
  padding: 0.1rem 0.4rem;
  font-size: 0.75rem;
  transition: all 0.2s;
}
.clear-btn:hover { border-color: var(--danger); color: var(--danger); }

/* Buttons */
.actions { display: flex; gap: 1rem; }
.btn-primary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--accent);
  color: #000;
  border: none;
  border-radius: 8px;
  padding: 0.6rem 1.6rem;
  font-weight: 700;
  font-size: 0.85rem;
  letter-spacing: 0.05em;
  transition: all 0.2s;
}
.btn-primary:hover:not(:disabled) { filter: brightness(1.15); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }

.spinner {
  width: 12px; height: 12px;
  border: 2px solid #00000044;
  border-top-color: #000;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Result card */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 1rem 1.2rem;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
}
.tag { padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: 700; }
.tag-ok { background: #39d98a22; color: var(--ok); border: 1px solid #39d98a44; }
.filename { font-weight: 500; font-size: 0.85rem; }
.meta { color: var(--muted); font-size: 0.78rem; margin-left: auto; }

.columns-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  padding: 0.8rem 1.2rem;
  border-bottom: 1px solid var(--border);
}
.col-chip {
  background: var(--bg-hover);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.15rem 0.6rem;
  font-size: 0.75rem;
  color: var(--muted);
}

.table-wrap {
  overflow-x: auto;
  padding: 0 1.2rem 1.2rem;
}
table { width: 100%; border-collapse: collapse; font-size: 0.78rem; margin-top: 0.8rem; }
th {
  text-align: left;
  color: var(--muted);
  padding: 0.4rem 0.8rem;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
  letter-spacing: 0.05em;
}
td {
  padding: 0.45rem 0.8rem;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--bg-hover); }

.index-section {
  padding: 1rem 1.2rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  border-top: 1px solid var(--border);
}
.index-ok { color: var(--ok); font-size: 0.82rem; }

.error-bar {
  background: #ff4d4d15;
  border: 1px solid #ff4d4d44;
  color: var(--danger);
  border-radius: 8px;
  padding: 0.7rem 1rem;
  font-size: 0.85rem;
}
</style>