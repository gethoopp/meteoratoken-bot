<template>
  <div class="panel">
    <h2>
      Big Wallet Holders
      <span v-if="holders.length" style="float:right;color:var(--muted);font-size:11px">
        {{ holders.length }} wallets
      </span>
    </h2>
    <div v-if="loading" class="empty">Loading...</div>
    <div v-else-if="!holders.length" class="empty">No big wallets found</div>
    <table v-else>
      <thead>
        <tr>
          <th>Address</th>
          <th>Amount</th>
          <th>Value USD</th>
          <th>% Supply</th>
          <th>Label</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="h in holders" :key="h.address">
          <td class="mono">
            {{ shortAddr(h.address) }}
            <span v-if="h.is_smart" class="badge smart" style="margin-left:6px">smart</span>
          </td>
          <td>{{ Number(h.amount).toLocaleString() }}</td>
          <td>${{ Number(h.value_usd).toLocaleString() }}</td>
          <td>{{ h.percentage.toFixed(2) }}%</td>
          <td>{{ h.label || '—' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
defineProps({
  holders: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})
function shortAddr(a) {
  if (!a) return ''
  return a.length > 12 ? `${a.slice(0, 6)}...${a.slice(-4)}` : a
}
</script>