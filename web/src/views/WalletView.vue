<template>
  <div>
    <div class="row wrap">
      <input
        v-model="address"
        class="input"
        style="flex:1;min-width:260px"
        placeholder="Enter wallet address (e.g. 5xxx...)"
        @keyup.enter="analyze"
      />
      <button class="btn" :disabled="!address || loading" @click="analyze">
        {{ loading ? 'Analyzing...' : 'Analyze' }}
      </button>
    </div>

    <div v-if="error" class="error-box" style="margin-top:12px">{{ error }}</div>

    <div style="margin-top:16px">
      <WalletAnalyzer :analysis="analysis" :loading="loading" />
    </div>

    <div v-if="address" class="panel">
      <h2>
        <span class="status-dot" :class="wsStatus"></span>
        Live Wallet Monitor
      </h2>
      <div v-if="!updates.length" class="empty">Waiting for account updates via WebSocket...</div>
      <div v-else>
        <div v-for="(u, i) in updates" :key="i" class="mono" style="font-size:12px;padding:6px 0;border-bottom:1px solid var(--border)">
          {{ u.ts }} — {{ JSON.stringify(u.data).slice(0, 120) }}...
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import api from '../services/api'
import { createWalletSocket } from '../services/websocket'
import WalletAnalyzer from '../components/WalletAnalyzer.vue'

const address = ref('')
const analysis = ref(null)
const loading = ref(false)
const error = ref(null)
const updates = ref([])
const wsStatus = ref('closed')
let socket = null

async function analyze() {
  if (!address.value) return
  loading.value = true
  error.value = null
  analysis.value = null
  updates.value = []
  cleanupSocket()
  try {
    analysis.value = await api.analyzeWallet(address.value.trim())
    startSocket(address.value.trim())
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function startSocket(addr) {
  socket = createWalletSocket(
    addr,
    (data) => {
      updates.value.unshift({ ts: new Date().toLocaleTimeString(), data })
      if (updates.value.length > 20) updates.value.pop()
    },
    (s) => { wsStatus.value = s }
  )
}

function cleanupSocket() {
  socket?.close()
  socket = null
}

onBeforeUnmount(cleanupSocket)
</script>