<template>
  <div class="angle-input">
    <div class="field">
      <label>入射角度 θ (°)</label>
      <el-input-number v-model="settings.incidenceAngle" :min="0" :max="84" :step="1" size="small" />
    </div>
    <div class="path-factor">
      路径因子: <strong>{{ settings.pathFactor.toFixed(4) }}</strong>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useSettingsStore } from '../stores/settings'
const settings = useSettingsStore()
</script>

<style scoped>
.angle-input { display: flex; flex-direction: column; gap: 8px; }
.field { display: flex; align-items: center; justify-content: space-between; }
.field label { font-size: 12px; min-width: 110px; color: var(--rcf-text); font-family: var(--rcf-font-mono); }
.path-factor { font-size: 12px; color: var(--rcf-text-secondary); font-family: var(--rcf-font-mono); }
.path-factor strong { color: var(--rcf-primary); }
</style>
