<template>
  <div class="linear-detectors">
    <h3>探测器序列</h3>
    <div class="det-toolbar">
      <el-button size="small" @click="addDetector('HD', 105)">+ HD</el-button>
      <el-button size="small" @click="addDetector('EBT', 280)">+ EBT</el-button>
      <el-button size="small" type="danger" @click="emit('update:detectors', [])">清空</el-button>
    </div>
    <el-table :data="detectors" border size="small" max-height="250" style="margin-top: 8px">
      <el-table-column type="index" label="#" width="40" />
      <el-table-column prop="material_name" label="类型" width="80" />
      <el-table-column label="厚度 (μm)" width="120">
        <template #default="{ row, $index }">
          <el-input-number
            :model-value="row.thickness"
            :min="1"
            size="small"
            controls-position="right"
            @update:model-value="(v: number | null) => updateThickness($index, Number(v ?? 0))"
          />
        </template>
      </el-table-column>
      <el-table-column label="" width="60">
        <template #default="{ $index }">
          <el-button size="small" type="danger" text @click="removeDetector($index)">×</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import type { StackLayer } from '../types'

const props = defineProps<{ detectors: StackLayer[] }>()
const emit = defineEmits<{ (e: 'update:detectors', v: StackLayer[]): void }>()

function createLayerId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `layer-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function addDetector(name: string, thickness: number) {
  const next: StackLayer[] = [
    ...props.detectors,
    {
      material_name: name,
      thickness,
      thickness_type: 'fixed' as const,
      is_detector: true,
      layer_id: createLayerId(),
    },
  ]
  emit('update:detectors', next)
}

function removeDetector(index: number) {
  emit(
    'update:detectors',
    props.detectors.filter((_, i) => i !== index),
  )
}

function updateThickness(index: number, thickness: number) {
  const next = props.detectors.map((item, i) => (i === index ? { ...item, thickness } : item))
  emit('update:detectors', next)
}
</script>

<style scoped>
.linear-detectors { flex: 1; min-width: 300px; }
.linear-detectors h3 { margin: 0 0 12px; color: var(--rcf-primary); }
.det-toolbar { display: flex; gap: 4px; }
</style>
