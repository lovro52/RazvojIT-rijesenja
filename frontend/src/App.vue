<template>
  <div class="app">
    <header class="header">
      <div class="header-inner">
        <div class="logo">
          <span class="logo-icon">⬡</span>
          <span class="logo-text">NETLOG<span class="accent">RAG</span></span>
        </div>
        <nav class="nav">
          <RouterLink to="/dashboard" class="nav-link"><span class="nav-icon">⊞</span> Dashboard</RouterLink>
          <RouterLink to="/upload"    class="nav-link"><span class="nav-icon">↑</span> Upload</RouterLink>
          <RouterLink to="/files"     class="nav-link"><span class="nav-icon">▣</span> Files</RouterLink>
          <RouterLink to="/filter"    class="nav-link"><span class="nav-icon">⊟</span> Filter</RouterLink>
          <RouterLink to="/ips"       class="nav-link"><span class="nav-icon">⊙</span> IP Stats</RouterLink>
          <RouterLink to="/compare"   class="nav-link"><span class="nav-icon">⇌</span> Usporedi</RouterLink>
          <RouterLink to="/query"     class="nav-link"><span class="nav-icon">⌕</span> Query</RouterLink>
          <RouterLink to="/history"   class="nav-link"><span class="nav-icon">◷</span> History</RouterLink>
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
  max-width: 1200px; margin: 0 auto; padding: 0 2rem;
  height: 64px; display: flex; align-items: center; justify-content: space-between;
}
.logo {
  display: flex; align-items: center; gap: 0.6rem;
  font-family: var(--font-head); font-weight: 800; font-size: 1.5rem; letter-spacing: 0.08em;
}
.logo-icon { color: var(--accent); font-size: 1.7rem; }
.accent { color: var(--accent); }
.nav { display: flex; gap: 0.5rem; }
.nav-link {
  display: flex; align-items: center; gap: 0.4rem;
  padding: 0.5rem 1rem; border-radius: 8px; text-decoration: none;
  color: var(--muted); font-size: 0.88rem; letter-spacing: 0.03em;
  transition: all 0.2s; border: 1px solid transparent;
}
.nav-link:hover { color: var(--text); background: var(--bg-hover); }
.nav-link.router-link-active { color: var(--accent); border-color: var(--accent-dim); background: var(--accent-dim); }
.main { flex: 1; max-width: 1200px; width: 100%; margin: 0 auto; padding: 2.5rem 2rem; }
</style>