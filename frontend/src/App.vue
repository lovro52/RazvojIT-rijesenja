<template>
  <div class="app">
    <header class="header">
      <div class="header-inner">
        <div class="logo">
          <span class="logo-icon">⬡</span>
          <span class="logo-text">NETLOG<span class="accent">RAG</span></span>
        </div>
        <nav class="nav">
          <RouterLink to="/dashboard"  class="nav-link"><span class="nav-icon">⊞</span> Dashboard</RouterLink>
          <RouterLink to="/upload"     class="nav-link"><span class="nav-icon">↑</span> Upload</RouterLink>
          <RouterLink to="/files"      class="nav-link"><span class="nav-icon">▣</span> Files</RouterLink>
          <RouterLink to="/filter"     class="nav-link"><span class="nav-icon">⊟</span> Filter</RouterLink>
          <RouterLink to="/ips"        class="nav-link"><span class="nav-icon">⊙</span> IP Stats</RouterLink>
          <RouterLink to="/compare"    class="nav-link"><span class="nav-icon">⇌</span> Usporedi</RouterLink>
          <RouterLink to="/models"     class="nav-link"><span class="nav-icon">◈</span> Modeli</RouterLink>
          <RouterLink to="/baseline"   class="nav-link"><span class="nav-icon">⊶</span> Baseline</RouterLink>
          <RouterLink to="/evaluation" class="nav-link"><span class="nav-icon">📊</span> Evaluacija</RouterLink>
          <RouterLink to="/query"      class="nav-link"><span class="nav-icon">⌕</span> Query</RouterLink>
          <RouterLink to="/history"    class="nav-link"><span class="nav-icon">◷</span> History</RouterLink>
          <RouterLink to="/about"      class="nav-link"><span class="nav-icon">ℹ</span> O sustavu</RouterLink>
        </nav>
      </div>
    </header>
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app { min-height: 100vh; display: flex; flex-direction: column; }
.header {
  border-bottom: 1px solid var(--border); background: var(--bg);
  position: sticky; top: 0; z-index: 100; backdrop-filter: blur(12px);
}
.header-inner {
  max-width: 1400px; margin: 0 auto; padding: 0 1.5rem;
  height: 56px; display: flex; align-items: center; justify-content: space-between; gap: 1rem;
}
.logo {
  display: flex; align-items: center; gap: 0.5rem;
  font-family: var(--font-head); font-weight: 800; font-size: 1.3rem;
  letter-spacing: 0.08em; flex-shrink: 0;
}
.logo-icon { color: var(--accent); font-size: 1.5rem; }
.accent { color: var(--accent); }
.nav { display: flex; gap: 0.2rem; flex-wrap: nowrap; overflow-x: auto; }
.nav::-webkit-scrollbar { display: none; }
.nav-link {
  display: flex; align-items: center; gap: 0.3rem;
  padding: 0.4rem 0.65rem; border-radius: 7px; text-decoration: none;
  color: var(--muted); font-size: 0.78rem; letter-spacing: 0.02em;
  transition: all 0.2s; border: 1px solid transparent; white-space: nowrap; flex-shrink: 0;
}
.nav-link:hover { color: var(--text); background: var(--bg-hover); }
.nav-link.router-link-active { color: var(--accent); border-color: var(--accent-dim); background: var(--accent-dim); }
.main { flex: 1; max-width: 1400px; width: 100%; margin: 0 auto; padding: 2rem 1.5rem; }
</style>