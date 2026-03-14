<template>
  <div class="spectrum-chart" ref="chartContainer">
    <v-chart
      v-if="option"
      ref="chartRef"
      :option="option"
      autoresize
      style="width: 100%; height: 100%;"
    />
    <el-empty v-else description="暂无能谱数据" :image-size="60" />
    <div v-if="analysisStore.cursorEnergy" class="cursor-label">
      E = {{ analysisStore.cursorEnergy.toFixed(2) }} MeV
    </div>
  </div>
</template>

<script setup>
import { computed, ref, shallowRef, onMounted, onBeforeUnmount, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, GridComponent,
  LegendComponent, ToolboxComponent, DataZoomComponent,
  MarkLineComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { useAnalysisStore } from '../../stores/analysis'
import { useSessionStore } from '../../stores/session'
import wsClient from '../../api/websocket'

use([
  CanvasRenderer, LineChart,
  TitleComponent, TooltipComponent, GridComponent,
  LegendComponent, ToolboxComponent, DataZoomComponent,
  MarkLineComponent,
])

const analysisStore = useAnalysisStore()
const sessionStore = useSessionStore()
const chartContainer = ref(null)
const chartRef = shallowRef(null)

function formatScientificLabel(value) {
  if (!Number.isFinite(value) || value <= 0) return ''

  const exponent = Math.round(Math.log10(value))
  if (Math.abs(value - 10 ** exponent) / value < 1e-8) {
    return `1e${exponent}`
  }

  const [coefficient, rawExponent] = value.toExponential(1).split('e')
  return `${coefficient}e${Number(rawExponent)}`
}

function handleClick(event) {
  const chart = chartRef.value
  if (!chart) return

  const rect = chartContainer.value.getBoundingClientRect()
  const offsetX = event.clientX - rect.left
  const offsetY = event.clientY - rect.top
  const pointInPixel = [offsetX, offsetY]

  if (chart.containPixel('grid', pointInPixel)) {
    const pointInGrid = chart.convertFromPixel({ seriesIndex: 0 }, pointInPixel)
    const energy = pointInGrid[0]
    if (energy > 0) {
      wsClient.setCursor(energy)
    }
  }
}

onMounted(() => {
  chartContainer.value.addEventListener('click', handleClick, true)
})

onBeforeUnmount(() => {
  if (chartContainer.value) {
    chartContainer.value.removeEventListener('click', handleClick, true)
  }
})

const option = computed(() => {
  const data = analysisStore.spectrumData
  if (!data || !data.energy) return null
  const gridColor = 'rgba(117, 136, 141, 0.18)'
  const axisColor = '#5c7077'
  const textColor = '#23363b'
  const primaryColor = '#205566'

  const cursorMarkLine = analysisStore.cursorEnergy ? {
    silent: true,
    symbol: 'none',
    animation: false,
    lineStyle: { color: textColor, width: 1.5, type: 'solid' },
    label: {
      show: true,
      position: 'insideEndTop',
      formatter: analysisStore.cursorEnergy.toFixed(2) + ' MeV',
      fontSize: 11,
      color: textColor,
    },
    data: [{ xAxis: analysisStore.cursorEnergy }],
  } : undefined

  const series = [
    {
      name: '能谱',
      type: 'line',
      data: data.energy.map((e, i) => [e, data.dNdE[i]]),
      smooth: false,
      lineStyle: { width: 1.75, color: primaryColor },
      symbol: 'none',
      markLine: cursorMarkLine,
    },
  ]

  if (data.noise_energy) {
    series.push({
      name: '噪声',
      type: 'line',
      data: data.noise_energy.map((e, i) => [e, data.noise_dNdE[i]]),
      smooth: false,
      lineStyle: { width: 1, type: 'dashed', color: '#8f6c4d' },
      symbol: 'none',
    })
  }

  const fit = analysisStore.fitResult
  if (fit && fit.success && fit.fit_curve) {
    series.push({
      name: `拟合 (kT=${fit.kT.toFixed(2)} MeV)`,
      type: 'line',
      data: fit.fit_curve.energy.map((e, i) => [e, fit.fit_curve.dNdE[i]]),
      smooth: true,
      lineStyle: { width: 2, color: '#e6a23c' },
      symbol: 'none',
    })
  }

  return {
    backgroundColor: 'transparent',
    title: {
      text: '能谱 dN/dE',
      left: 'center',
      textStyle: { fontSize: 14, color: textColor, fontFamily: 'IBM Plex Sans' },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(251, 253, 252, 0.95)',
      borderColor: 'rgba(117, 136, 141, 0.2)',
      textStyle: { color: textColor },
      formatter: params => {
        return params.map((item) => (
          `${item.marker}${item.seriesName}: E = ${item.value[0].toFixed(2)} MeV<br/>dN/dE = ${item.value[1].toExponential(2)}`
        )).join('<br/>')
      },
    },
    legend: { bottom: 0, textStyle: { color: axisColor } },
    grid: { left: 92, right: 24, top: 48, bottom: 48 },
    xAxis: {
      type: 'value',
      name: 'E (MeV)',
      min: sessionStore.params.specEmin,
      max: sessionStore.params.specEmax,
      nameTextStyle: { color: axisColor },
      axisLabel: { color: axisColor },
      axisLine: { lineStyle: { color: gridColor } },
      splitLine: { lineStyle: { color: gridColor } },
    },
    yAxis: {
      type: 'log',
      name: 'dN/dE',
      min: sessionStore.params.specdNdEmin,
      max: sessionStore.params.specdNdEmax,
      nameTextStyle: { color: axisColor },
      axisLabel: {
        color: axisColor,
        formatter: (value) => formatScientificLabel(value),
      },
      axisLine: { lineStyle: { color: gridColor } },
      splitLine: { lineStyle: { color: gridColor } },
      minorSplitLine: { show: true, lineStyle: { color: 'rgba(117, 136, 141, 0.08)' } },
    },
    toolbox: {
      feature: {
        dataZoom: { yAxisIndex: 'none' },
        restore: {},
        saveAsImage: {},
      },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0 },
    ],
    series,
  }
})
</script>

<style scoped>
.spectrum-chart {
  flex: 1;
  min-height: 250px;
  padding: 10px;
  border: 1px solid var(--tps-border);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
  position: relative;
}

.cursor-label {
  position: absolute;
  bottom: 44px;
  right: 40px;
  background: rgba(35, 54, 59, 0.84);
  color: #fff;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  pointer-events: none;
}
</style>
