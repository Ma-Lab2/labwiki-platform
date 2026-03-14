import { defineStore } from 'pinia'
import { ref } from 'vue'
import wsClient from '../api/websocket'

export const useAnalysisStore = defineStore('analysis', () => {
  const imagePng = ref('')
  const spectrumData = ref(null)
  const cutoffEnergy = ref(0)
  const parabolaData = ref(null)
  const fitResult = ref(null)
  const batchSpectrumPng = ref('')
  const batchSpectra = ref([])
  const comparisonPng = ref('')
  const cursorEnergy = ref(null)

  function setupListeners() {
    wsClient.on('analysis_result', (data) => {
      imagePng.value = data.image_png
      spectrumData.value = data.spectrum_data
      cutoffEnergy.value = data.cutoff
      parabolaData.value = data.parabola
    })

    wsClient.on('image_update', (data) => {
      imagePng.value = data.image_png
    })

    wsClient.on('cursor_update', (data) => {
      cursorEnergy.value = data.energy || null
    })

    wsClient.on('batch_result', (data) => {
      batchSpectrumPng.value = data.spectrum_png
      batchSpectra.value = data.spectra
    })

    wsClient.on('compare_result', (data) => {
      comparisonPng.value = data.comparison_png
    })

    wsClient.on('fit_result', (data) => {
      fitResult.value = data
    })

    wsClient.on('export_data', (data) => {
      // Trigger download
      const blob = new Blob([data.content], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = data.filename || 'spectrum.txt'
      a.click()
      URL.revokeObjectURL(url)
    })
  }

  function selectImage(path) {
    cursorEnergy.value = null
    wsClient.selectImage(path)
  }

  function batchAnalyze(filePaths) {
    wsClient.batchAnalyze(filePaths)
  }

  function compare(filePaths, options) {
    wsClient.compare(filePaths, options)
  }

  function fitSpectrum(EfitMin, EfitMax) {
    wsClient.fit(EfitMin, EfitMax)
  }

  function exportSpectrum() {
    wsClient.exportSpectrum()
  }

  return {
    imagePng, spectrumData, cutoffEnergy, parabolaData,
    fitResult, batchSpectrumPng, batchSpectra, comparisonPng,
    cursorEnergy,
    setupListeners, selectImage, batchAnalyze, compare,
    fitSpectrum, exportSpectrum,
  }
})
