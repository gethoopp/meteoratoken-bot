<template>
  <div class="panel">
    <h2>Token Info</h2>
    <div v-if="!info" class="empty">No token data yet</div>
    <div v-else>
      <div class="row" style="margin-bottom:12px">
        <strong style="font-size:16px">{{ info.symbol || '—' }}</strong>
        <span class="mono" style="color:var(--muted)">{{ shortMint(info.mint) }}</span>
        <span v-if="info.dex" class="badge yellow">{{ info.dex }}</span>
      </div>
      <div class="grid cols-3">
        <div class="stat">
          <div class="label">Price USD</div>
          <div class="value">${{ fmt(info.price_usd) }}</div>
        </div>
        <div class="stat">
          <div class="label">Price SOL</div>
          <div class="value">{{ fmt(info.price_sol) }}</div>
        </div>
        <div class="stat">
          <div class="label">Market Cap</div>
          <div class="value">${{ fmt(info.market_cap) }}</div>
        </div>
        <div class="stat">
          <div class="label">Liquidity</div>
          <div class="value">${{ fmt(info.liquidity) }}</div>
        </div>
        <div class="stat">
          <div class="label">Volume 24h</div>
          <div class="value">${{ fmt(info.volume_24h) }}</div>
        </div>
        <div class="stat">
          <div class="label">Change 24h</div>
          <div class="value" :class="info.price_change_24h >= 0 ? 'pos' : 'neg'">
            {{ info.price_change_24h >= 0 ? '+' : '' }}{{ info.price_change_24h }}%
          </div>
        </div>
      </div>
      <div class="grid cols-3" style="margin-top:12px">
        <div class="stat">
          <div class="label">Change 1h</div>
          <div class="value" :class="info.price_change_1h >= 0 ? 'pos' : 'neg'">
            {{ info.price_change_1h >= 0 ? '+' : '' }}{{ info.price_change_1h }}%
          </div>
        </div>
        <div class="stat">
          <div class="label">Change 5m</div>
          <div class="value" :class="info.price_change_5m >= 0 ? 'pos' : 'neg'">
            {{ info.price_change_5m >= 0 ? '+' : '' }}{{ info.price_change_5m }}%
          </div>
        </div>
        <div class="stat">
          <div class="label">Holders</div>
          <div class="value">{{ info.holders_count || '—' }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({ info: { type: Object, default: null } })
function fmt(n) {
  if (n == null) return '—'
  if (Math.abs(n) < 0.0001 && n !== 0) return n.toExponential(4)
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: 6 })
}
function shortMint(m) {
  if (!m) return ''
  return m.length > 16 ? `${m.slice(0, 8)}...${m.slice(-6)}` : m
}
</script>