import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { RCFResult, EnergyScanResponse, LinearDesignResponse } from '../types'

export const useComputeStore = defineStore('compute', () => {
  // Energy scan results
  const rcfResults = ref<RCFResult[]>([])
  const resEneMatrix = ref<number[][]>([])
  const energyRange = ref<number[]>([])

  // Linear design results
  const linearEnergySeq = ref<number[]>([])
  const linearAlSeq = ref<number[]>([])
  const linearMessages = ref<string[]>([])

  // Progress state
  const isComputing = ref(false)
  const progressPercent = ref(0)
  const progressMessage = ref('')

  function setEnergyScanResult(result: EnergyScanResponse) {
    rcfResults.value = result.rcf_results
    resEneMatrix.value = result.res_ene_matrix
    energyRange.value = result.energy_range
  }

  function setLinearDesignResult(result: LinearDesignResponse) {
    linearEnergySeq.value = result.energy_sequence
    linearAlSeq.value = result.al_thickness_sequence
    linearMessages.value = result.messages
  }

  function setProgress(message: string, percent: number) {
    progressMessage.value = message
    progressPercent.value = percent
  }

  function startComputing() {
    isComputing.value = true
    progressPercent.value = 0
    progressMessage.value = ''
  }

  function stopComputing() {
    isComputing.value = false
    progressPercent.value = 100
  }

  return {
    rcfResults, resEneMatrix, energyRange,
    linearEnergySeq, linearAlSeq, linearMessages,
    isComputing, progressPercent, progressMessage,
    setEnergyScanResult, setLinearDesignResult,
    setProgress, startComputing, stopComputing,
  }
})
