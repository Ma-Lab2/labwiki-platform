<template>
  <div ref="plotEl" class="plot-container"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import Plotly from 'plotly.js-dist-min'
import { useComputeStore } from '../stores/compute'
import { useSettingsStore } from '../stores/settings'

const compute = useComputeStore()
const settings = useSettingsStore()
const plotEl = ref<HTMLElement>()

const PALETTE = ['#00d2ff', '#ff6b6b', '#51cf66', '#ffd43b', '#cc5de8', '#ff922b', '#20c997', '#748ffc']

const THEME_BG: Record<string, string> = {
  'electric-blue': '#1e1e2e',
  'matrix-green': '#0a0a0a',
  'red-alert': '#1a0a0a',
}

function render() {
  if (!plotEl.value || compute.rcfResults.length === 0) return

  const bg = THEME_BG[settings.theme] || '#1e1e2e'
  const traces = compute.rcfResults.map((rcf, i) => ({
    x: rcf.edep_curve_x,
    y: rcf.edep_curve_y,
    mode: 'lines' as const,
    name: `${rcf.name} #${rcf.rcf_id + 1}`,
    line: { color: PALETTE[i % PALETTE.length], width: 1.5 },
  }))

  const layout = {
    title: { text: '能量沉积曲线', font: { color: '#e0e0e0' } },
    xaxis: { title: '入射能量 (MeV)', color: '#aaa', gridcolor: '#333' },
    yaxis: { title: '沉积能量 (MeV)', color: '#aaa', gridcolor: '#333' },
    paper_bgcolor: bg,
    plot_bgcolor: bg,
    font: { color: '#e0e0e0' },
    margin: { t: 40, r: 20, b: 50, l: 60 },
    showlegend: true,
    legend: { font: { color: '#ccc' } },
  }

  Plotly.react(plotEl.value, traces, layout, { responsive: true })
}

onMounted(render)
watch(() => [compute.rcfResults, settings.theme], render, { deep: true })
</script>

<style scoped>
.plot-container { width: 100%; height: 350px; }
</style>
