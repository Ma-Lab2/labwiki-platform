<template>
  <div class="file-list">
    <el-input
      v-model="searchText"
      size="small"
      placeholder="搜索文件..."
      clearable
      style="margin-bottom: 6px;"
    />
    <el-scrollbar max-height="300px">
      <div
        v-for="file in filteredFiles"
        :key="file.name"
        :class="['file-item', { active: file.name === sessionStore.currentFile }]"
        @click="selectFile(file)"
      >
        <span class="file-name">{{ file.name }}</span>
        <span class="file-size">{{ formatSize(file.size) }}</span>
      </div>
      <el-empty v-if="filteredFiles.length === 0" description="无图像文件" :image-size="40" />
    </el-scrollbar>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useSessionStore } from '../../stores/session'
import { useAnalysisStore } from '../../stores/analysis'
import api from '../../api/index'

const sessionStore = useSessionStore()
const analysisStore = useAnalysisStore()
const files = ref([])
const searchText = ref('')

const filteredFiles = computed(() => {
  if (!searchText.value) return files.value
  const q = searchText.value.toLowerCase()
  return files.value.filter(f => f.name.toLowerCase().includes(q))
})

watch(() => sessionStore.imagePath, () => loadFiles())

onMounted(() => {
  analysisStore.setupListeners()
  loadFiles()
})

async function loadFiles() {
  if (!sessionStore.imagePath) return
  try {
    const res = await api.listFiles(sessionStore.imagePath)
    files.value = res.data.files
    // Warning already shown by DirectoryBrowser, no need to duplicate
  } catch (e) {
    files.value = []
    ElMessage.warning('加载文件列表失败')
  }
}

function selectFile(file) {
  sessionStore.currentFile = file.name
  const fullPath = sessionStore.imagePath + '/' + file.name
  analysisStore.selectImage(fullPath)
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}
</script>

<style scoped>
.file-list {
  padding: 0 8px 8px;
}

.file-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 10px;
  cursor: pointer;
  border-radius: 10px;
  font-size: 12px;
  transition: background-color 0.16s ease, color 0.16s ease;
}

.file-item:hover {
  background: rgba(32, 85, 102, 0.08);
}

.file-item.active {
  background: var(--tps-primary);
  color: white;
}

.file-size {
  color: var(--tps-text-muted);
  font-size: 11px;
  font-family: var(--tps-font-mono);
}

.file-item.active .file-size {
  color: rgba(255, 255, 255, 0.8);
}
</style>
