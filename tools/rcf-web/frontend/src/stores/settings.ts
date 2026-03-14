import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useSettingsStore = defineStore('settings', () => {
  const theme = ref<'electric-blue' | 'matrix-green' | 'red-alert'>('electric-blue')
  const locale = ref<'zh-CN' | 'en-US'>('zh-CN')
  const incidenceAngle = ref(0)
  const pathFactor = computed(() =>
    incidenceAngle.value > 0
      ? 1.0 / Math.cos((incidenceAngle.value * Math.PI) / 180)
      : 1.0
  )
  const ionKey = ref('proton')
  const energyMin = ref(0.5)
  const energyMax = ref(100.0)
  const energyStep = ref(0.1)

  return {
    theme, locale, incidenceAngle, pathFactor, ionKey,
    energyMin, energyMax, energyStep,
  }
})
