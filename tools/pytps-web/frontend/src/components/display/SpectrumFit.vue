<template>
  <div class="spectrum-fit">
    <el-form inline size="small">
      <el-form-item label="拟合范围">
        <el-input-number v-model="fitMin" :min="0" :max="500" :step="0.5" :precision="1" style="width: 90px;" />
        <span style="margin: 0 4px;">~</span>
        <el-input-number v-model="fitMax" :min="0" :max="500" :step="1" :precision="1" style="width: 90px;" />
        <span style="margin-left: 4px;">MeV</span>
      </el-form-item>
      <el-form-item>
        <el-button type="warning" size="small" @click="doFit" :disabled="!analysisStore.spectrumData">拟合</el-button>
      </el-form-item>
    </el-form>
    <div v-if="analysisStore.fitResult" class="fit-result">
      <template v-if="analysisStore.fitResult.success">
        <el-tag type="success">kT = {{ analysisStore.fitResult.kT.toFixed(3) }} ± {{ analysisStore.fitResult.sigma_kT.toFixed(3) }} MeV</el-tag>
        <el-tag>R² = {{ analysisStore.fitResult.R2.toFixed(4) }}</el-tag>
      </template>
      <el-tag v-else type="danger">{{ analysisStore.fitResult.message }}</el-tag>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAnalysisStore } from '../../stores/analysis'

const analysisStore = useAnalysisStore()
const fitMin = ref(5)
const fitMax = ref(30)

function doFit() {
  analysisStore.fitSpectrum(fitMin.value, fitMax.value)
}
</script>

<style scoped>
.spectrum-fit {
  padding: 8px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid var(--tps-border);
  border-radius: 18px;
}

.fit-result {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
