<template>
  <div class="linear-design">
    <div class="linear-top">
      <LinearDesignParams
        :al-thick1="alThick1"
        :energy-interval="energyInterval"
        :al-min="alMin"
        :al-max="alMax"
        :al-interval="alInterval"
        :loading="compute.isComputing"
        @update:al-thick1="v => (alThick1 = v)"
        @update:energy-interval="v => (energyInterval = v)"
        @update:al-min="v => (alMin = v)"
        @update:al-max="v => (alMax = v)"
        @update:al-interval="v => (alInterval = v)"
        @run="runDesign"
      />

      <LinearDesignDetectors
        :detectors="detectors"
        @update:detectors="v => (detectors = v)"
      />
    </div>

    <LinearDesignResults
      :visible="compute.linearEnergySeq.length > 0"
      :rows="resultRows"
      :messages="compute.linearMessages"
      @transfer="transferToMain"
    />

    <div ref="plotEl" class="plot-container"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Plotly from 'plotly.js-dist-min'
import { useComputeStore } from '../stores/compute'
import { useStackStore } from '../stores/stack'
import { useSettingsStore } from '../stores/settings'
import { linearDesign } from '../api/compute'
import type { StackLayer } from '../types'
import LinearDesignParams from './LinearDesignParams.vue'
import LinearDesignDetectors from './LinearDesignDetectors.vue'
import LinearDesignResults from './LinearDesignResults.vue'

const compute = useComputeStore()
const stack = useStackStore()
const settings = useSettingsStore()

const alThick1 = ref(30)
const energyInterval = ref(2.0)
const alMin = ref(0)
const alMax = ref(1000)
const alInterval = ref(1.0)
const detectors = ref<StackLayer[]>([])
const plotEl = ref<HTMLElement>()

const resultRows = computed(() =>
  compute.linearEnergySeq.map((e, i) => ({
    index: i + 1,
    energy: e.toFixed(2),
    alThickness: compute.linearAlSeq[i]?.toFixed(1) ?? '-',
  })),
)

async function runDesign() {
  if (detectors.value.length === 0) return
  compute.startComputing()
  try {
    const result = await linearDesign({
      detectors: detectors.value,
      al_thick_1: alThick1.value,
      energy_interval: energyInterval.value,
      al_thick_min: alMin.value,
      al_thick_max: alMax.value,
      al_interval: alInterval.value,
      incidence_angle: settings.incidenceAngle,
    })
    compute.setLinearDesignResult(result)
    renderPlot()
  } finally {
    compute.stopComputing()
  }
}

function transferToMain() {
  const seq = compute.linearEnergySeq
  const alSeq = compute.linearAlSeq
  stack.clearAll()
  for (let i = 0; i < seq.length && i < detectors.value.length; i++) {
    stack.addLayer({ material_name: 'Al', thickness: alSeq[i], thickness_type: 'variable', is_detector: false })
    stack.addLayer({ ...detectors.value[i] })
  }
}

function renderPlot() {
  if (!plotEl.value || compute.linearEnergySeq.length === 0) return
  const x = compute.linearEnergySeq.map((_, i) => i + 1)
  const y = compute.linearEnergySeq

  Plotly.react(
    plotEl.value,
    [
      {
        x,
        y,
        mode: 'lines+markers',
        marker: { color: '#00d2ff', size: 8 },
        line: { color: '#00d2ff', width: 2 },
        text: compute.linearAlSeq.map(a => `Al: ${a.toFixed(1)} μm`),
      },
    ],
    {
      title: { text: '线性设计结果', font: { color: '#e0e0e0' } },
      xaxis: { title: 'RCF #', color: '#aaa', gridcolor: '#333' },
      yaxis: { title: '截止能量 (MeV)', color: '#aaa', gridcolor: '#333' },
      paper_bgcolor: '#1e1e2e',
      plot_bgcolor: '#1e1e2e',
      font: { color: '#e0e0e0' },
      margin: { t: 40, r: 20, b: 50, l: 60 },
    },
    { responsive: true },
  )
}

watch(
  () => compute.linearEnergySeq,
  renderPlot,
  { deep: true },
)
</script>

<style scoped>
.linear-design { padding: 16px; }
.linear-top { display: flex; gap: 24px; flex-wrap: wrap; }
.plot-container { width: 100%; height: 350px; margin-top: 16px; }
</style>
