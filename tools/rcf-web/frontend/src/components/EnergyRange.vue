<template>
  <div class="energy-range">
    <div class="field">
      <label>E_min (MeV)</label>
      <el-input-number v-model="settings.energyMin" :min="0.1" :max="1000" :step="0.1" size="small" />
    </div>
    <div class="field">
      <label>E_max (MeV)</label>
      <el-input-number v-model="settings.energyMax" :min="1" :max="2000" :step="1" size="small" />
    </div>
    <div class="field">
      <label>E_step (MeV)</label>
      <el-input-number v-model="settings.energyStep" :min="0.01" :max="10" :step="0.05" size="small" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useSettingsStore } from '../stores/settings'
const settings = useSettingsStore()
</script>

<style scoped>
.energy-range { display: flex; flex-direction: column; gap: 8px; }
.field { display: flex; align-items: center; justify-content: space-between; }
.field label { font-size: 12px; min-width: 90px; color: var(--rcf-text); font-family: var(--rcf-font-mono); }
</style>
