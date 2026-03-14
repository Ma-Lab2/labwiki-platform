<template>
  <div ref="plotEl" class="plot-container"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import Plotly from 'plotly.js-dist-min'
import { useComputeStore } from '../stores/compute'
import { PLOT_THEME } from '../theme'

const compute = useComputeStore()
const plotEl = ref<HTMLElement>()

function render() {
  if (!plotEl.value || compute.rcfResults.length === 0) return

  const x = compute.rcfResults.map(r => r.rcf_id + 1)
  const y = compute.rcfResults.map(r => r.cutoff_energy ?? 0)
  const text = compute.rcfResults.map(r => `${r.name} #${r.rcf_id + 1}`)

  const trace = {
    x, y, text,
    mode: 'lines+markers' as const,
    marker: { color: PLOT_THEME.accent, size: 8 },
    line: { color: PLOT_THEME.accent, width: 2 },
    name: '截止能量',
  }

  const layout = {
    title: { text: '截止能量 vs RCF 编号', font: { color: PLOT_THEME.text, family: 'IBM Plex Sans' } },
    xaxis: { title: 'RCF #', color: PLOT_THEME.muted, gridcolor: PLOT_THEME.grid, zerolinecolor: PLOT_THEME.grid },
    yaxis: { title: '截止能量 (MeV)', color: PLOT_THEME.muted, gridcolor: PLOT_THEME.grid, zerolinecolor: PLOT_THEME.grid },
    paper_bgcolor: PLOT_THEME.panel,
    plot_bgcolor: PLOT_THEME.panel,
    font: { color: PLOT_THEME.text, family: 'IBM Plex Sans' },
    margin: { t: 40, r: 20, b: 50, l: 60 },
  }

  Plotly.react(plotEl.value, [trace], layout, { responsive: true })
}

onMounted(render)
watch(() => compute.rcfResults, render, { deep: true })
</script>

<style scoped>
.plot-container { width: 100%; height: 350px; }
</style>
