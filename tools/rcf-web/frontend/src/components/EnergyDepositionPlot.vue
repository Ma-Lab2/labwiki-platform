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

  const traces = compute.rcfResults.map((rcf, i) => ({
    x: rcf.edep_curve_x,
    y: rcf.edep_curve_y,
    mode: 'lines' as const,
    name: `${rcf.name} #${rcf.rcf_id + 1}`,
    line: { color: PLOT_THEME.palette[i % PLOT_THEME.palette.length], width: 2 },
  }))

  const layout = {
    title: { text: '能量沉积曲线', font: { color: PLOT_THEME.text, family: 'IBM Plex Sans' } },
    xaxis: { title: '入射能量 (MeV)', color: PLOT_THEME.muted, gridcolor: PLOT_THEME.grid, zerolinecolor: PLOT_THEME.grid },
    yaxis: { title: '沉积能量 (MeV)', color: PLOT_THEME.muted, gridcolor: PLOT_THEME.grid, zerolinecolor: PLOT_THEME.grid },
    paper_bgcolor: PLOT_THEME.panel,
    plot_bgcolor: PLOT_THEME.panel,
    font: { color: PLOT_THEME.text, family: 'IBM Plex Sans' },
    margin: { t: 40, r: 20, b: 50, l: 60 },
    showlegend: true,
    legend: { font: { color: PLOT_THEME.muted, family: 'IBM Plex Sans' } },
  }

  Plotly.react(plotEl.value, traces, layout, { responsive: true })
}

onMounted(render)
watch(() => compute.rcfResults, render, { deep: true })
</script>

<style scoped>
.plot-container { width: 100%; height: 350px; }
</style>
