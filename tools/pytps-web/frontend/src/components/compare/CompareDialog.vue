<template>
  <el-dialog
    v-model="visible"
    title="质子谱线对比 (Proton Spectrum Comparison)"
    width="80%"
    top="5vh"
    destroy-on-close
  >
    <div class="compare-content">
      <div class="compare-controls">
        <CompareControls
          :files="files"
          v-model:selectedFiles="selectedFiles"
          v-model:yRange="yRange"
          v-model:gamma="gamma"
          v-model:colorMin="colorMin"
          v-model:colorMax="colorMax"
          v-model:energyTicks="energyTicks"
        />
        <div class="compare-actions">
          <el-button type="primary" @click="generate" :loading="loading">生成对比图</el-button>
          <el-button @click="clear">清除</el-button>
        </div>
      </div>
      <div class="compare-result">
        <img v-if="analysisStore.comparisonPng" :src="'data:image/png;base64,' + analysisStore.comparisonPng" class="compare-image" />
        <el-empty v-else description="请选择图像并生成对比图" />
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import CompareControls from './CompareControls.vue'
import { useSessionStore } from '../../stores/session'
import { useAnalysisStore } from '../../stores/analysis'
import api from '../../api/index'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const sessionStore = useSessionStore()
const analysisStore = useAnalysisStore()

const files = ref([])
const selectedFiles = ref([])
const yRange = ref(80)
const gamma = ref(1.0)
const colorMin = ref(0)
const colorMax = ref(65536)
const energyTicks = ref('')
const loading = ref(false)

watch(visible, async (val) => {
  if (val) {
    try {
      const res = await api.listFiles(sessionStore.imagePath)
      files.value = res.data.files.map(f => f.name)
    } catch (e) {
      files.value = []
    }
  }
})

async function generate() {
  if (selectedFiles.value.length === 0) return
  loading.value = true

  const filePaths = selectedFiles.value.map(f => sessionStore.imagePath + '/' + f)

  analysisStore.compare(filePaths, {
    y_range_px: yRange.value,
    gamma: gamma.value,
    color_min: colorMin.value,
    color_max: colorMax.value,
    cmap: sessionStore.params.cmap,
    custom_energy_ticks: energyTicks.value,
  })

  // Wait for result via WebSocket
  const unwatch = watch(() => analysisStore.comparisonPng, () => {
    loading.value = false
    unwatch()
  })
}

function clear() {
  analysisStore.comparisonPng = ''
  selectedFiles.value = []
}
</script>

<style scoped>
.compare-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.compare-controls {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.compare-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.compare-result {
  max-height: 60vh;
  overflow: auto;
  text-align: center;
}

.compare-image {
  max-width: 100%;
}
</style>
