<template>
  <div>
    <TokenSearch v-model="mint" :loading="store.loading" @search="onSearch" />

    <div v-if="store.error" class="error-box" style="margin-top:12px">
      {{ store.error }}
    </div>

    <div v-if="store.info || store.loading" style="margin-top:16px">
      <TokenInfo :info="store.info" />

      <div class="grid cols-2">
        <PriceChart :points="pricePoints" :status="wsStatus" />
        <WhaleList :holders="store.holders" :loading="store.loading" />
      </div>

      <TransactionFeed :transactions="store.transactions" :loading="store.loading" />
    </div>
    <div v-else class="empty panel" style="margin-top:16px">
      Search a token mint to see real-time price, big wallets, and transactions.
    </div>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, watch } from 'vue'
import { useTokenStore } from '../stores/token'
import { createTokenSocket } from '../services/websocket'
import TokenSearch from '../components/TokenSearch.vue'
import TokenInfo from '../components/TokenInfo.vue'
import PriceChart from '../components/PriceChart.vue'
import WhaleList from '../components/WhaleList.vue'
import TransactionFeed from '../components/TransactionFeed.vue'

const store = useTokenStore()
const mint = ref('')
const pricePoints = ref([])
const wsStatus = ref('closed')
let socket = null

async function onSearch(m) {
  if (!m) return
  cleanupSocket()
  pricePoints.value = []
  await store.loadAll(m)
  if (store.info) startSocket(m)
}

function startSocket(m) {
  socket = createTokenSocket(
    m,
    (data) => {
      store.updatePrice(data)
      pricePoints.value.push({ t: new Date().toLocaleTimeString(), price: data.price_usd })
      if (pricePoints.value.length > 60) pricePoints.value.shift()
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