<template>
  <div class="image-display">
    <div v-if="analysisStore.imagePng" class="image-container">
      <img :src="'data:image/png;base64,' + analysisStore.imagePng" alt="TPS Image" class="tps-image" />
    </div>
    <el-empty v-else description="请选择图像文件" :image-size="80" />
  </div>
</template>

<script setup>
import { useAnalysisStore } from '../../stores/analysis'

const analysisStore = useAnalysisStore()
</script>

<style scoped>
.image-display {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid var(--tps-border);
  border-radius: 18px;
  overflow: hidden;
}

.image-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tps-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 12px;
  box-shadow: 0 10px 24px rgba(24, 49, 55, 0.12);
}
</style>
