<template>
  <div class="app">
    <header class="header">
      <div class="header-inner">

        <RouterLink to="/dashboard" class="logo">
          <span class="logo-icon">⬡</span>
          <span class="logo-text">NETLOG<span class="accent">RAG</span></span>
        </RouterLink>

        <nav class="nav" @mouseleave="open = null">
          <RouterLink to="/dashboard" class="nav-item">
            <span class="ni-icon">⊞</span> Dashboard
          </RouterLink>

          <div
            v-for="g in groups" :key="g.id"
            class="nav-group"
            @mouseenter="open = g.id"
          >
            <button
              class="nav-item"
              :class="{ active: isActive(g), opened: open === g.id }"
              @click="open = open === g.id ? null : g.id"
            >
              <span class="ni-icon">{{ g.icon }}</span> {{ g.label }}
              <span class="caret">▾</span>
            </button>

            <transition name="drop">
              <div v-if="open === g.id" class="dropdown">
                <RouterLink
                  v-for="l in g.links" :key="l.to"
                  :to="l.to" class="drop-item" @click="open = null"
                >
                  <span class="di-icon">{{ l.icon }}</span>
                  <span class="di-text">
                    <span class="di-name">{{ l.name }}</span>
                    <span class="di-desc">{{ l.desc }}</span>
                  </span>
                </RouterLink>
              </div>
            </transition>
          </div>
        </nav>

        <RouterLink to="/about" class="about-link" title="O sustavu">
          <span>ℹ</span>
        </RouterLink>

        <button class="burger" @click="mobile = !mobile" aria-label="Izbornik">
          <span></span><span></span><span></span>
        </button>
      </div>

      <transition name="drop">
        <div v-if="mobile" class="mobile-menu">
          <RouterLink to="/dashboard" class="mm-link" @click="mobile = false">
            Dashboard
          </RouterLink>
          <div v-for="g in groups" :key="g.id" class="mm-group">
            <div class="mm-title">{{ g.icon }} {{ g.label }}</div>
            <RouterLink
              v-for="l in g.links" :key="l.to"
              :to="l.to" class="mm-link indent" @click="mobile = false"
            >{{ l.name }}</RouterLink>
          </div>
          <RouterLink to="/about" class="mm-link" @click="mobile = false">
            O sustavu
          </RouterLink>
        </div>
      </transition>
    </header>

    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route  = useRoute()
const open   = ref(null)
const mobile = ref(false)

const groups = [
  {
    id: 'data', label: 'Podaci', icon: '▤',
    links: [
      { to: '/upload', icon: '↑', name: 'Upload',        desc: 'Učitaj i indeksiraj CSV' },
      { to: '/files',  icon: '▣', name: 'Datoteke',      desc: 'Pregled učitanih datoteka' },
      { to: '/filter', icon: '⊟', name: 'Filter',        desc: 'Pretraga po IP-u i protokolu' },
      { to: '/ips',    icon: '⊙', name: 'IP statistike', desc: 'Detalji po adresi' },
    ],
  },
  {
    id: 'analysis', label: 'Analiza', icon: '⌕',
    links: [
      { to: '/query',      icon: '⌕', name: 'Upit',          desc: 'RAG izvještaj iz dohvaćenih dokaza' },
      { to: '/classifier', icon: '◉', name: 'Klasifikator',  desc: 'Fine-tunani model — tip napada' },
      { to: '/compare',    icon: '⇌', name: 'Usporedi',      desc: 'Keyword vs semantička pretraga' },
      { to: '/history',    icon: '◷', name: 'Povijest',      desc: 'Prethodni upiti' },
    ],
  },
  {
    id: 'eval', label: 'Evaluacija', icon: '◈',
    links: [
      { to: '/models',     icon: '◈', name: 'Modeli',   desc: 'Usporedba LLM modela' },
      { to: '/baseline',   icon: '⊶', name: 'Baseline', desc: 'XGBoost i Random Forest' },
      { to: '/evaluation', icon: '▦', name: 'Metrike',  desc: 'Rezultati po datasetu' },
    ],
  },
]

function isActive(g) {
  return g.links.some(l => route.path === l.to)
}

watch(() => route.path, () => { open.value = null; mobile.value = false })
</script>

<style scoped>
.app { min-height: 100vh; display: flex; flex-direction: column; }

.header {
  border-bottom: 1px solid var(--border);
  background: var(--bg);
  backdrop-filter: blur(12px);
  position: sticky; top: 0; z-index: 200;
}
.header-inner {
  max-width: 1400px; margin: 0 auto; padding: 0 1.5rem;
  height: 60px; display: flex; align-items: center; gap: 2rem;
}

.logo {
  display: flex; align-items: center; gap: .5rem; text-decoration: none;
  font-family: var(--font-head); font-weight: 800; font-size: 1.25rem;
  letter-spacing: .08em; color: var(--text); flex-shrink: 0;
}
.logo-icon { color: var(--accent); font-size: 1.45rem; }
.accent    { color: var(--accent); }

.nav { display: flex; gap: .25rem; flex: 1; }
.nav-group { position: relative; }

.nav-item {
  display: flex; align-items: center; gap: .4rem;
  padding: .5rem .85rem; border-radius: 8px;
  font-size: .85rem; font-family: inherit; letter-spacing: .02em;
  color: var(--muted); background: none; border: 1px solid transparent;
  text-decoration: none; cursor: pointer; white-space: nowrap;
  transition: color .15s, background .15s, border-color .15s;
}
.nav-item:hover { color: var(--text); background: var(--bg-hover); }
.nav-item.active,
.nav-item.router-link-active {
  color: var(--accent); background: var(--accent-dim); border-color: var(--accent-dim);
}
.ni-icon { font-size: .95rem; }
.caret   { font-size: .6rem; opacity: .6; margin-left: .1rem; transition: transform .18s; }
.nav-item.opened .caret { transform: rotate(180deg); }

.dropdown {
  position: absolute; top: calc(100% + .4rem); left: 0; min-width: 270px;
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; padding: .4rem; z-index: 300;
  box-shadow: 0 12px 32px rgba(0, 0, 0, .45);
  display: flex; flex-direction: column; gap: .1rem;
}
.drop-item {
  display: flex; align-items: flex-start; gap: .7rem;
  padding: .55rem .7rem; border-radius: 8px;
  text-decoration: none; color: var(--text); transition: background .15s;
}
.drop-item:hover { background: var(--bg-hover); }
.drop-item.router-link-active { background: var(--accent-dim); }
.drop-item.router-link-active .di-name { color: var(--accent); }
.di-icon { color: var(--accent); font-size: .9rem; width: 1.1rem; flex-shrink: 0; margin-top: .1rem; }
.di-text { display: flex; flex-direction: column; gap: .1rem; }
.di-name { font-size: .84rem; font-weight: 600; }
.di-desc { font-size: .72rem; color: var(--muted); line-height: 1.35; }

.about-link {
  display: flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
  color: var(--muted); text-decoration: none; font-size: 1rem;
  border: 1px solid var(--border); transition: all .15s;
}
.about-link:hover { color: var(--accent); border-color: var(--accent); }
.about-link.router-link-active { color: var(--accent); border-color: var(--accent); background: var(--accent-dim); }

.burger { display: none; flex-direction: column; gap: 4px; background: none;
          border: none; cursor: pointer; padding: .4rem; }
.burger span { width: 20px; height: 2px; background: var(--muted); border-radius: 2px; }

.mobile-menu {
  border-top: 1px solid var(--border); background: var(--bg-card);
  padding: .8rem 1.5rem 1.2rem; display: flex; flex-direction: column; gap: .2rem;
}
.mm-group { margin-top: .6rem; }
.mm-title { font-size: .7rem; color: var(--muted); letter-spacing: .08em;
            text-transform: uppercase; padding: .3rem 0; }
.mm-link  { padding: .5rem .2rem; font-size: .88rem; color: var(--text);
            text-decoration: none; border-radius: 6px; }
.mm-link.indent { padding-left: 1rem; color: var(--muted); }
.mm-link.router-link-active { color: var(--accent); }

.drop-enter-active, .drop-leave-active { transition: opacity .15s, transform .15s; }
.drop-enter-from, .drop-leave-to { opacity: 0; transform: translateY(-6px); }

.main { flex: 1; max-width: 1400px; width: 100%; margin: 0 auto; padding: 2rem 1.5rem; }

@media (max-width: 900px) {
  .nav, .about-link { display: none; }
  .burger { display: flex; }
  .header-inner { justify-content: space-between; gap: 1rem; }
}
</style>