<template>
  <Teleport to="body">
    <div v-if="compute.isComputing" class="progress-overlay">
      <div class="progress-card">
        <h3>计算中...</h3>
        <el-progress :percentage="Math.round(compute.progressPercent)" :stroke-width="20" />
        <p class="progress-msg">{{ compute.progressMessage }}</p>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useComputeStore } from '../stores/compute'
const compute = useComputeStore()
</script>

<style scoped>
.progress-overlay {
  position: fixed;
  inset: 0;
  background: rgba(22, 37, 41, 0.28);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.progress-card {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.5), rgba(255, 255, 255, 0)),
    var(--rcf-bg-card-strong);
  border: 1px solid var(--rcf-border-strong);
  border-radius: 22px;
  box-shadow: var(--rcf-shadow-soft);
  padding: 28px 36px;
  min-width: 400px;
  text-align: center;
}
.progress-card h3 {
  color: var(--rcf-primary-strong);
  margin: 0 0 16px;
  font-family: var(--rcf-font-display);
  font-size: 1.45rem;
}
.progress-msg {
  color: var(--rcf-text-secondary);
  font-size: 13px;
  margin-top: 12px;
}
</style>
