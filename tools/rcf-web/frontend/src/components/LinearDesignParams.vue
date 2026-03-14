<template>
  <div class="linear-params">
    <h3>线性设计参数</h3>
    <div class="field">
      <label>初始 Al 厚度 (μm)</label>
      <el-input-number
        :model-value="alThick1"
        :min="0"
        :max="5000"
        :step="10"
        size="small"
        @update:model-value="(v: number | null) => emit('update:alThick1', Number(v ?? 0))"
      />
    </div>
    <div class="field">
      <label>能量间隔 (MeV)</label>
      <el-input-number
        :model-value="energyInterval"
        :min="0.1"
        :max="50"
        :step="0.5"
        size="small"
        @update:model-value="(v: number | null) => emit('update:energyInterval', Number(v ?? 0))"
      />
    </div>
    <div class="field">
      <label>Al 搜索最小 (μm)</label>
      <el-input-number
        :model-value="alMin"
        :min="0"
        :max="5000"
        :step="10"
        size="small"
        @update:model-value="(v: number | null) => emit('update:alMin', Number(v ?? 0))"
      />
    </div>
    <div class="field">
      <label>Al 搜索最大 (μm)</label>
      <el-input-number
        :model-value="alMax"
        :min="0"
        :max="10000"
        :step="100"
        size="small"
        @update:model-value="(v: number | null) => emit('update:alMax', Number(v ?? 0))"
      />
    </div>
    <div class="field">
      <label>搜索步长 (μm)</label>
      <el-input-number
        :model-value="alInterval"
        :min="0.1"
        :max="100"
        :step="0.5"
        size="small"
        @update:model-value="(v: number | null) => emit('update:alInterval', Number(v ?? 0))"
      />
    </div>
    <el-button type="primary" :loading="loading" style="margin-top: 12px" @click="emit('run')">
      开始线性设计
    </el-button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  alThick1: number
  energyInterval: number
  alMin: number
  alMax: number
  alInterval: number
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update:alThick1', v: number): void
  (e: 'update:energyInterval', v: number): void
  (e: 'update:alMin', v: number): void
  (e: 'update:alMax', v: number): void
  (e: 'update:alInterval', v: number): void
  (e: 'run'): void
}>()
</script>

<style scoped>
.linear-params { flex: 1; min-width: 300px; }
.linear-params h3 { margin: 0 0 12px; color: var(--rcf-primary); }
.field { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.field label { font-size: 13px; min-width: 140px; }
</style>
