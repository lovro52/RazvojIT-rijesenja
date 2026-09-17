import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import DashboardView  from './views/DashboardView.vue'
import UploadView     from './views/UploadView.vue'
import FilesView      from './views/FilesView.vue'
import FilterView     from './views/FilterView.vue'
import IPStatsView    from './views/IPStatsView.vue'
import CompareView    from './views/CompareView.vue'
import ModelsView     from './views/ModelsView.vue'
import BaselineView   from './views/BaselineView.vue'
import ClassifierView from './views/ClassifierView.vue'
import EvaluationView from './views/EvaluationView.vue'
import QueryView      from './views/QueryView.vue'
import HistoryView    from './views/HistoryView.vue'
import AboutView      from './views/AboutView.vue'
import './style.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',           redirect: '/dashboard' },
    { path: '/dashboard',  component: DashboardView },
    { path: '/upload',     component: UploadView },
    { path: '/files',      component: FilesView },
    { path: '/filter',     component: FilterView },
    { path: '/ips',        component: IPStatsView },
    { path: '/compare',    component: CompareView },
    { path: '/models',     component: ModelsView },
    { path: '/baseline',   component: BaselineView },
    { path: '/classifier', component: ClassifierView },
    { path: '/evaluation', component: EvaluationView },
    { path: '/query',      component: QueryView },
    { path: '/history',    component: HistoryView },
    { path: '/about',      component: AboutView },
  ]
})

createApp(App).use(router).mount('#app')