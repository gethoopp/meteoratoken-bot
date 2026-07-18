<template>
  <div class="panel">
    <h2>
      <span class="status-dot" :class="status"></span>
      Real-time Price Chart
    </h2>
    <div v-if="!points.length" class="empty">Waiting for WebSocket data...</div>
    <div v-else>
      <div class="row" style="margin-bottom:8px">
        <span class="mono" style="color:var(--muted);font-size:12px">{{ points.length }} ticks</span>
        <span class="spacer"></span>
        <span>Latest: <strong>${{ fmt(last) }}</strong></span>
      </div>
      <canvas ref="canvasEl" style="width:100%;height:200px"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Filler
} from 'chart.js'

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler)

const props = defineProps({
  points: { type: Array, default: () => [] },
  status: { type: String, default: 'closed' }
})

const canvasEl = ref(null)
let chart = null

function fmt(n) {
  if (n == null) return '—'
  if (Math.abs(n) < 0.0001 && n !== 0) return n.toExponential(4)
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: 8 })
}

const last = ref(0)
watch(
  () => props.points,
  (pts) => {
    if (!pts.length) return
    last.value = pts[pts.length - 1].price
    if (!chart || !canvasEl.value) return
    chart.data.labels = pts.map((p) => p.t)
    chart.data.datasets[0].data = pts.map((p) => p.price)
    chart.update('none')
  },
  { deep: true }
)

onMounted(() => {
  if (!canvasEl.value) return
  chart = new Chart(canvasEl.value, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'Price USD',
          data: [],
          borderColor: '#4f8cff',
          backgroundColor: 'rgba(79,140,255,0.15)',
          fill: true,
          tension: 0.25,
          pointRadius: 0,
          borderWidth: 2
        }
      ]
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { display: false },
        y: { ticks: { color: '#8a90a6', font: { size: 10 } }, grid: { color: '#2a2f40' } }
      }
    }
  })
})

onBeforeUnmount(() => chart?.destroy())
</script>