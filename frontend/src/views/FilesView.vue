<template>
  <div class="files-view">

    <div class="page-header">
      <h1>Uploaded Files</h1>
      <p class="subtitle">All CSV files that have been uploaded and indexed into the system.</p>
    </div>

    <button class="btn-refresh" @click="loadFiles">
      <span :class="{ spinning: loading }">↻</span> Refresh
    </button>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else-if="files.length === 0" class="empty">
      <p>No files uploaded yet. Go to <RouterLink to="/upload">Upload</RouterLink> to add logs.</p>
    </div>

    <div v-else class="file-list">
      <div v-for="f in files" :key="f.filename" class="file-card">
        <div class="file-top">
          <span class="file-name">{{ f.filename }}</span>
          <span class="tag" :class="f.indexed ? 'tag-ok' : 'tag-warn'">
            {{ f.indexed ? '✓ Indexed' : '⏳ Not indexed' }}
          </span>
        </div>
        <div class="file-meta">
          <span class="meta-item"><span class="meta-key">rows</span> {{ f.rows }}</span>
          <span class="meta-item"><span class="meta-key">uploaded</span> {{ formatDate(f.uploaded_at) }}</span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const files   = ref([])
const loading = ref(false)

async function loadFiles() {
  loading.value = true
  try {
    const { data } = await axios.get('/logs/files')
    files.value = data.files
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

onMounted(loadFiles)
</script>

<style scoped>
.files-view { display: flex; flex-direction: column; gap: 1.5rem; }

.page-header h1 {
  font-family: var(--font-head); font-size: 1.8rem;
  font-weight: 800; letter-spacing: -0.02em; margin-bottom: 0.3rem;
}
.subtitle { color: var(--muted); font-size: 0.85rem; }

.btn-refresh {
  display: flex; align-items: center; gap: 0.4rem;
  background: var(--bg-card); border: 1px solid var(--border);
  color: var(--muted); border-radius: 7px; padding: 0.45rem 1rem;
  font-size: 0.82rem; transition: all 0.2s; width: fit-content;
}
.btn-refresh:hover { border-color: var(--accent); color: var(--accent); }
.spinning { display: inline-block; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.loading { color: var(--muted); font-size: 0.85rem; }

.empty {
  background: var(--bg-card); border: 1px dashed var(--border);
  border-radius: 12px; padding: 2.5rem; text-align: center;
  color: var(--muted); font-size: 0.85rem;
}
.empty a { color: var(--accent); text-decoration: none; }

.file-list { display: flex; flex-direction: column; gap: 0.8rem; }

.file-card {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 10px; padding: 1rem 1.2rem;
  display: flex; flex-direction: column; gap: 0.5rem;
  transition: border-color 0.2s;
}
.file-card:hover { border-color: var(--accent); }

.file-top { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
.file-name { font-weight: 500; font-size: 0.88rem; word-break: break-all; }

.tag { padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.72rem; font-weight: 700; }
.tag-ok   { background: #39d98a22; color: var(--ok);   border: 1px solid #39d98a44; }
.tag-warn { background: #ffb34722; color: var(--warn); border: 1px solid #ffb34744; }

.file-meta { display: flex; gap: 1.5rem; flex-wrap: wrap; }
.meta-item { font-size: 0.78rem; color: var(--muted); }
.meta-key { color: var(--muted); margin-right: 0.3rem; }
</style>