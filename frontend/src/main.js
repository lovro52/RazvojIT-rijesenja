import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import DashboardView from './views/DashboardView.vue'
import UploadView from './views/UploadView.vue'
import QueryView from './views/QueryView.vue'
import FilesView from './views/FilesView.vue'
import FilterView from './views/FilterView.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',          redirect: '/dashboard' },
    { path: '/dashboard', component: DashboardView },
    { path: '/upload',    component: UploadView },
    { path: '/files',     component: FilesView },
    { path: '/filter',    component: FilterView },
    { path: '/query',     component: QueryView },
  ]
})

createApp(App).use(router).mount('#app')