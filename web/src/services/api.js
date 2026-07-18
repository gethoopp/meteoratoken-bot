import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8000',
  timeout: 15000
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail || err.message
    return Promise.reject(new Error(msg))
  }
)

export default {
  async getToken(mint) {
    const { data } = await api.get(`/api/token/${mint}`)
    return data
  },
  async getHolders(mint, minValueUsd = 1000) {
    const { data } = await api.get(`/api/token/${mint}/holders`, {
      params: { min_value_usd: minValueUsd }
    })
    return data
  },
  async getTransactions(mint, limit = 20) {
    const { data } = await api.get(`/api/token/${mint}/transactions`, {
      params: { limit }
    })
    return data
  },
  async analyzeWallet(address) {
    const { data } = await api.get(`/api/wallet/${address}/analyze`)
    return data
  },
  async health() {
    const { data } = await api.get('/api/health')
    return data
  }
}