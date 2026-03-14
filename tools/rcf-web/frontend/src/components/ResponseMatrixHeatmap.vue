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
  if (!plotEl.value || compute.resEneMatrix.length === 0) return

  const trace = {
    z: compute.resEneMatrix,
    type: 'heatmap' as const,
    colorscale: PLOT_THEME.heatmap,
    colorbar: {
      title: { text: 'E (MeV)', font: { color: PLOT_THEME.muted, family: 'IBM Plex Sans' } },
      tickfont: { color: PLOT_THEME.muted, family: 'IBM Plex Sans' },
    },
  }

  const layout = {
    title: { text: '响应矩阵', font: { color: PLOT_THEME.text, family: 'IBM Plex Sans' } },
    xaxis: { title: '层编号', color: PLOT_THEME.muted, gridcolor: PLOT_THEME.grid },
    yaxis: { title: '入射能量索引', color: PLOT_THEME.muted, gridcolor: PLOT_THEME.grid },
    paper_bgcolor: PLOT_THEME.panel,
    plot_bgcolor: PLOT_THEME.panel,
    font: { color: PLOT_THEME.text, family: 'IBM Plex Sans' },
    margin: { t: 40, r: 20, b: 50, l: 60 },
  }

  Plotly.react(plotEl.value, [trace], layout, { responsive: true })
}

onMounted(render)
watch(() => compute.resEneMatrix, render, { deep: true })
</script>

<style scoped>
.plot-container { width: 100%; height: 400px; }
</style>
