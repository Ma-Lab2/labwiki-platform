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

const THEME_COLORS: Record<string, { primary: string; bg: string }> = {
  'electric-blue': { primary: '#00d2ff', bg: '#1e1e2e' },
  'matrix-green': { primary: '#00ff00', bg: '#0a0a0a' },
  'red-alert': { primary: '#ff4444', bg: '#1a0a0a' },
}

function render() {
  if (!plotEl.value || compute.rcfResults.length === 0) return

  const colors = THEME_COLORS[settings.theme] || THEME_COLORS['electric-blue']
  const x = compute.rcfResults.map(r => r.rcf_id + 1)
  const y = compute.rcfResults.map(r => r.cutoff_energy ?? 0)
  const text = compute.rcfResults.map(r => `${r.name} #${r.rcf_id + 1}`)

  const trace = {
    x, y, text,
    mode: 'lines+markers' as const,
    marker: { color: colors.primary, size: 8 },
    line: { color: colors.primary, width: 2 },
    name: '截止能量',
  }

  const layout = {
    title: { text: '截止能量 vs RCF 编号', font: { color: '#e0e0e0' } },
    xaxis: { title: 'RCF #', color: '#aaa', gridcolor: '#333' },
    yaxis: { title: '截止能量 (MeV)', color: '#aaa', gridcolor: '#333' },
    paper_bgcolor: colors.bg,
    plot_bgcolor: colors.bg,
    font: { color: '#e0e0e0' },
    margin: { t: 40, r: 20, b: 50, l: 60 },
  }

  Plotly.react(plotEl.value, [trace], layout, { responsive: true })
}

onMounted(render)
watch(() => [compute.rcfResults, settings.theme], render, { deep: true })
</script>

<style scoped>
.plot-container { width: 100%; height: 350px; }
</style>
