<template>
  <div class="param-panel">
    <h3>参数设置</h3>
    <EnergyRange />
    <AngleInput />
    <IonSelector />
  </div>
</template>

<script setup lang="ts">
import EnergyRange from './EnergyRange.vue'
import AngleInput from './AngleInput.vue'
import IonSelector from './IonSelector.vue'
</script>

<style scoped>
.param-panel {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.param-panel h3 {
  margin: 0 0 8px;
  color: var(--rcf-primary);
  font-family: var(--rcf-font-mono);
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 1px;
}
</style>
