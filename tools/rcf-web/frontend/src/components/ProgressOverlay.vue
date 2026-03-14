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
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.progress-card {
  background: var(--rcf-bg, #1e1e2e);
  border: 1px solid var(--rcf-primary, #00d2ff);
  border-radius: 8px;
  padding: 32px 48px;
  min-width: 400px;
  text-align: center;
}
.progress-card h3 { color: var(--rcf-primary, #00d2ff); margin: 0 0 16px; }
.progress-msg { color: #aaa; font-size: 13px; margin-top: 12px; }
</style>
