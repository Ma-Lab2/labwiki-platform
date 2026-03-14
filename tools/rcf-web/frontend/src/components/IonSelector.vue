<template>
  <div class="ion-selector">
    <label>粒子类型</label>
    <el-select v-model="settings.ionKey" size="small" style="width: 100%">
      <el-option
        v-for="ion in ION_OPTIONS"
        :key="ion.value"
        :label="ion.label"
        :value="ion.value"
      />
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { useSettingsStore } from '../stores/settings'
import { ION_OPTIONS } from '../types'
const settings = useSettingsStore()
</script>

<style scoped>
.ion-selector { display: flex; flex-direction: column; gap: 4px; }
.ion-selector label { font-size: 12px; color: var(--rcf-text); font-family: var(--rcf-font-mono); }
</style>
