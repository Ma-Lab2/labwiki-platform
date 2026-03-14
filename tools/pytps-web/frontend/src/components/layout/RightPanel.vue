<template>
  <el-main class="right-panel">
    <div class="display-area">
      <div class="image-section">
        <ImageDisplay />
      </div>
      <div class="spectrum-section">
        <SpectrumChart />
        <SpectrumFit />
      </div>
    </div>
    <div class="action-bar">
      <el-button type="primary" size="small" @click="exportSpectrum">导出能谱</el-button>
      <el-button size="small" @click="showCompare = true">质子谱线对比</el-button>
    </div>
    <CompareDialog v-model="showCompare" />
  </el-main>
</template>

<script setup>
import { ref } from 'vue'
import ImageDisplay from '../display/ImageDisplay.vue'
import SpectrumChart from '../display/SpectrumChart.vue'
import SpectrumFit from '../display/SpectrumFit.vue'
import CompareDialog from '../compare/CompareDialog.vue'
import { useAnalysisStore } from '../../stores/analysis'

const analysisStore = useAnalysisStore()
const showCompare = ref(false)

function exportSpectrum() {
  analysisStore.exportSpectrum()
}
</script>

<style scoped>
.right-panel {
  display: flex;
  flex-direction: column;
  padding: 14px;
  border: 1px solid var(--tps-border);
  border-radius: 22px;
  background: var(--tps-panel-strong);
  box-shadow: var(--tps-shadow-card);
  overflow: hidden;
}

.display-area {
  flex: 1;
  display: flex;
  gap: 12px;
  overflow: hidden;
}

.image-section {
  flex: 1;
  min-width: 0;
}

.spectrum-section {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.action-bar {
  padding: 12px 4px 2px;
  display: flex;
  gap: 8px;
}

@media (max-width: 1100px) {
  .display-area {
    flex-direction: column;
  }
}
</style>
