<template>
  <div class="panel">
    <h2>Recent Transactions</h2>
    <div v-if="loading" class="empty">Loading...</div>
    <div v-else-if="!transactions.length" class="empty">No transactions found</div>
    <table v-else>
      <thead>
        <tr>
          <th>Type</th>
          <th>From</th>
          <th>To</th>
          <th>Amount</th>
          <th>Time</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="tx in transactions" :key="tx.signature">
          <td>
            <span class="badge" :class="tx.type === 'SWAP' ? 'yellow' : 'green'">
              {{ tx.type }}
            </span>
          </td>
          <td class="mono">{{ shortAddr(tx.from_address) }}</td>
          <td class="mono">{{ shortAddr(tx.to_address) }}</td>
          <td>{{ Number(tx.amount).toLocaleString() }}</td>
          <td class="mono">{{ fmtTime(tx.timestamp) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
defineProps({
  transactions: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})
function shortAddr(a) {
  if (!a) return ''
  return a.length > 12 ? `${a.slice(0, 6)}...${a.slice(-4)}` : a
}
function fmtTime(ts) {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleTimeString()
}
</script>