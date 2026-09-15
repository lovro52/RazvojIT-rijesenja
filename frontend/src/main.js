import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',           redirect: '/dashboard' },
    { path: '/dashboard',  component: () => import('./views/DashboardView.vue') },
    { path: '/upload',     component: () => import('./views/UploadView.vue') },
    { path: '/files',      component: () => import('./views/FilesView.vue') },
    { path: '/filter',     component: () => import('./views/FilterView.vue') },
    { path: '/ips',        component: () => import('./views/IPStatsView.vue') },
    { path: '/compare',    component: () => import('./views/CompareView.vue') },
    { path: '/models',     component: () => import('./views/ModelsView.vue') },
    { path: '/baseline',   component: () => import('./views/BaselineView.vue') },
    { path: '/evaluation', component: () => import('./views/EvaluationView.vue') },
    { path: '/query',      component: () => import('./views/QueryView.vue') },
    { path: '/history',    component: () => import('./views/HistoryView.vue') },
    { path: '/about',      component: () => import('./views/AboutView.vue') },
  ]
})

createApp(App).use(router).mount('#app')
