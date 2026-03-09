import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import UploadView from './views/UploadView.vue'
import QueryView from './views/QueryView.vue'
import FilesView from './views/FilesView.vue'
import FilterView from './views/FilterView.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',        redirect: '/upload' },
    { path: '/upload',  component: UploadView },
    { path: '/query',   component: QueryView },
    { path: '/files',   component: FilesView },
    { path: '/filter',  component: FilterView },
  ]
})

createApp(App).use(router).mount('#app')