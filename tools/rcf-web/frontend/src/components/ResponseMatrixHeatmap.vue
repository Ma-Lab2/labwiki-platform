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

const THEME_BG: Record<string, string> = {
  'electric-blue': '#1e1e2e',
  'matrix-green': '#0a0a0a',
  'red-alert': '#1a0a0a',
}

function render() {
  if (!plotEl.value || compute.resEneMatrix.length === 0) return

  const bg = THEME_BG[settings.theme] || '#1e1e2e'

  const trace = {
    z: compute.resEneMatrix,
    type: 'heatmap' as const,
    colorscale: 'Viridis',
    colorbar: {
      title: { text: 'E (MeV)', font: { color: '#ccc' } },
      tickfont: { color: '#ccc' },
    },
  }

  const layout = {
    title: { text: '响应矩阵', font: { color: '#e0e0e0' } },
    xaxis: { title: '层编号', color: '#aaa' },
    yaxis: { title: '入射能量索引', color: '#aaa' },
    paper_bgcolor: bg,
    plot_bgcolor: bg,
    font: { color: '#e0e0e0' },
    margin: { t: 40, r: 20, b: 50, l: 60 },
  }

  Plotly.react(plotEl.value, [trace], layout, { responsive: true })
}

onMounted(render)
watch(() => [compute.resEneMatrix, settings.theme], render, { deep: true })
</script>

<style scoped>
.plot-container { width: 100%; height: 400px; }
</style>
