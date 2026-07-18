import { defineStore } from 'pinia'
import api from '../services/api'

export const useTokenStore = defineStore('token', {
  state: () => ({
    mint: '',
    info: null,
    holders: [],
    transactions: [],
    loading: false,
    error: null
  }),
  actions: {
    async loadAll(mint) {
      this.mint = mint
      this.loading = true
      this.error = null
      try {
        const [info, holders, transactions] = await Promise.all([
          api.getToken(mint),
          api.getHolders(mint).catch(() => []),
          api.getTransactions(mint).catch(() => [])
        ])
        this.info = info
        this.holders = holders
        this.transactions = transactions
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    updatePrice(data) {
      if (!this.info) {
        this.info = { mint: this.mint, ...data }
      } else {
        this.info = { ...this.info, ...data }
      }
    },
    reset() {
      this.mint = ''
      this.info = null
      this.holders = []
      this.transactions = []
      this.error = null
    }
  }
})