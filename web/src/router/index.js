import { createRouter, createWebHistory } from 'vue-router'
import TokenView from '../views/TokenView.vue'
import WalletView from '../views/WalletView.vue'

const routes = [
  { path: '/', redirect: '/token' },
  { path: '/token', name: 'token', component: TokenView },
  { path: '/wallet', name: 'wallet', component: WalletView }
]

export default createRouter({
  history: createWebHistory(),
  routes
})