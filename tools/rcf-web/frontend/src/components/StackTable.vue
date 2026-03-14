<template>
  <el-table
    :data="stack.layers"
    border
    size="small"
    highlight-current-row
    @current-change="handleCurrentChange"
    style="width: 100%"
    max-height="400"
  >
    <el-table-column type="index" label="#" width="40" />
    <el-table-column prop="material_name" label="材料" width="100" />
    <el-table-column label="厚度 (μm)" width="120">
      <template #default="{ row, $index }">
        <el-input-number
          v-model="row.thickness"
          :min="0"
          :step="1"
          size="small"
          controls-position="right"
          @change="(val: number) => stack.updateThickness($index, val)"
        />
      </template>
    </el-table-column>
    <el-table-column prop="thickness_type" label="类型" width="80">
      <template #default="{ row }">
        <el-tag :type="row.thickness_type === 'fixed' ? 'info' : 'success'" size="small">
          {{ row.thickness_type === 'fixed' ? '固定' : '可变' }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column label="探测器" width="70">
      <template #default="{ row }">
        <el-tag v-if="row.is_detector" type="warning" size="small">RCF</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="截止能量" width="100">
      <template #default="{ row }">
        <span v-if="getCutoff(row)">{{ getCutoff(row)?.toFixed(2) }} MeV</span>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { useStackStore } from '../stores/stack'
import { useComputeStore } from '../stores/compute'
import type { StackLayer } from '../types'

const stack = useStackStore()
const compute = useComputeStore()
const emit = defineEmits<{ (e: 'select', index: number): void }>()

function handleCurrentChange(row: StackLayer) {
  const idx = stack.layers.indexOf(row)
  emit('select', idx)
}

function getCutoff(row: StackLayer): number | null {
  if (!row.is_detector) return null
  const rowIndex = stack.layers.indexOf(row)
  const rcf = compute.rcfResults.find(r => {
    if (row.layer_id && r.layer_id) return r.layer_id === row.layer_id
    return r.table_id === rowIndex
  })
  return rcf?.cutoff_energy ?? null
}
</script>
