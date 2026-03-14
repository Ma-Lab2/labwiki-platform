import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { StackLayer } from '../types'

function createLayerId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `layer-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function normalizeLayer(layer: StackLayer): StackLayer {
  return { ...layer, layer_id: layer.layer_id ?? createLayerId() }
}

export const useStackStore = defineStore('stack', () => {
  const layers = ref<StackLayer[]>([])

  function addLayer(layer: StackLayer) {
    layers.value.push(normalizeLayer(layer))
  }

  function removeLayer(index: number) {
    layers.value.splice(index, 1)
  }

  function moveUp(index: number) {
    if (index <= 0) return
    const tmp = layers.value[index]
    layers.value[index] = layers.value[index - 1]
    layers.value[index - 1] = tmp
  }

  function moveDown(index: number) {
    if (index >= layers.value.length - 1) return
    const tmp = layers.value[index]
    layers.value[index] = layers.value[index + 1]
    layers.value[index + 1] = tmp
  }

  function clearAll() {
    layers.value = []
  }

  function importFromJson(data: StackLayer[]) {
    layers.value = data.map(normalizeLayer)
  }

  function exportToJson(): StackLayer[] {
    return JSON.parse(JSON.stringify(layers.value))
  }

  function updateThickness(index: number, thickness: number) {
    if (layers.value[index]) {
      layers.value[index].thickness = thickness
    }
  }

  return {
    layers,
    addLayer, removeLayer, moveUp, moveDown,
    clearAll, importFromJson, exportToJson, updateThickness,
  }
})
