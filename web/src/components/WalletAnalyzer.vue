<template>
  <div class="panel">
    <h2>Wallet Analysis</h2>
    <div v-if="loading" class="empty">Analyzing wallet...</div>
    <div v-else-if="!analysis" class="empty">Enter a wallet address to analyze</div>
    <div v-else>
      <div class="grid cols-3">
        <div class="stat">
          <div class="label">Total Txs</div>
          <div class="value">{{ analysis.total_txs }}</div>
        </div>
        <div class="stat">
          <div class="label">Swaps</div>
          <div class="value">{{ analysis.swaps }}</div>
        </div>
        <div class="stat">
          <div class="label">NFT Trades</div>
          <div class="value">{{ analysis.nft_trades }}</div>
        </div>
        <div class="stat">
          <div class="label">Transfers</div>
          <div class="value">{{ analysis.transfers }}</div>
        </div>
        <div class="stat">
          <div class="label">Win Rate</div>
          <div class="value">{{ analysis.win_rate != null ? analysis.win_rate + '%' : '—' }}</div>
        </div>
        <div class="stat">
          <div class="label">Avg Hold Time</div>
          <div class="value">{{ analysis.avg_hold_time || '—' }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  analysis: { type: Object, default: null },
  loading: { type: Boolean, default: false }
})
</script>