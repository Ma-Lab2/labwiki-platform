<template>
  <div class="compare-controls-form">
    <el-form size="small" label-width="100px">
      <el-form-item label="选择图像">
        <el-select
          v-model="selectedFilesModel"
          multiple
          filterable
          placeholder="选择要对比的图像"
          style="width: 100%;"
        >
          <el-option v-for="f in files" :key="f" :label="f" :value="f" />
        </el-select>
      </el-form-item>
      <el-form-item label="能量刻度">
        <el-input v-model="energyTicksModel" placeholder="例如: 5, 10, 15, 20 或留空自动" />
      </el-form-item>
      <el-form-item label="Y显示范围">
        <el-input-number v-model="yRangeModel" :min="20" :max="300" :step="10" />
        <span style="margin-left: 4px;">px</span>
      </el-form-item>
      <el-form-item label="Gamma校正">
        <el-input-number v-model="gammaModel" :min="0.01" :max="10" :step="0.05" :precision="2" />
      </el-form-item>
      <el-form-item label="Colorbar">
        <el-input-number v-model="colorMinModel" :min="0" :max="100000" :step="100" style="width: 100px;" />
        <span style="margin: 0 4px;">~</span>
        <el-input-number v-model="colorMaxModel" :min="1" :max="100000" :step="1000" style="width: 100px;" />
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  files: Array,
  selectedFiles: Array,
  yRange: Number,
  gamma: Number,
  colorMin: Number,
  colorMax: Number,
  energyTicks: String,
})

const emit = defineEmits([
  'update:selectedFiles', 'update:yRange', 'update:gamma',
  'update:colorMin', 'update:colorMax', 'update:energyTicks',
])

const selectedFilesModel = computed({
  get: () => props.selectedFiles,
  set: v => emit('update:selectedFiles', v),
})
const yRangeModel = computed({
  get: () => props.yRange,
  set: v => emit('update:yRange', v),
})
const gammaModel = computed({
  get: () => props.gamma,
  set: v => emit('update:gamma', v),
})
const colorMinModel = computed({
  get: () => props.colorMin,
  set: v => emit('update:colorMin', v),
})
const colorMaxModel = computed({
  get: () => props.colorMax,
  set: v => emit('update:colorMax', v),
})
const energyTicksModel = computed({
  get: () => props.energyTicks,
  set: v => emit('update:energyTicks', v),
})
</script>

<style scoped>
.compare-controls-form {
  flex: 1;
}
</style>
