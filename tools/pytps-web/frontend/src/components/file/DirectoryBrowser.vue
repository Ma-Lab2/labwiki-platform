<template>
  <div class="dir-browser">
    <el-input
      v-model="currentPath"
      size="small"
      placeholder="图像目录路径（容器内挂载目录）"
      @keyup.enter="browse"
    >
      <template #append>
        <el-button @click="browse" :icon="FolderOpened" />
      </template>
    </el-input>
    <div v-if="parentDir" class="parent-link">
      <el-link type="primary" @click="goUp">..</el-link>
    </div>
    <p class="browser-note">只能浏览已挂载到容器内的目录。当前默认根目录通常是 <code>/data/images</code>。</p>
    <div v-for="dir in dirs" :key="dir" class="dir-item">
      <el-link type="primary" @click="enterDir(dir)">{{ dir }}/</el-link>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { FolderOpened } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useSessionStore } from '../../stores/session'
import api from '../../api/index'

const sessionStore = useSessionStore()
const currentPath = ref('')
const dirs = ref([])
const parentDir = ref(null)

watch(() => sessionStore.imagePath, (val) => {
  currentPath.value = val
  browse()
})

onMounted(() => {
  if (sessionStore.imagePath) {
    currentPath.value = sessionStore.imagePath
    browse()
  }
})

async function browse() {
  try {
    const res = await api.browseDirectory(currentPath.value)
    dirs.value = res.data.dirs
    parentDir.value = res.data.parent
    sessionStore.imagePath = res.data.current
    if (res.data.warning) {
      ElMessage.warning(res.data.warning)
    }
  } catch (e) {
    console.error('Browse failed:', e)
    ElMessage.warning('目录不存在或无法访问: ' + currentPath.value)
  }
}

function enterDir(dir) {
  currentPath.value = currentPath.value + '/' + dir
  browse()
}

function goUp() {
  if (parentDir.value) {
    currentPath.value = parentDir.value
    browse()
  }
}
</script>

<style scoped>
.dir-browser {
  padding: 8px;
}

.parent-link,
.dir-item {
  padding: 3px 8px;
}

.dir-item :deep(.el-link),
.parent-link :deep(.el-link) {
  font-family: var(--tps-font-mono);
  font-size: 12px;
}

.browser-note {
  margin: 8px 8px 10px;
  color: var(--tps-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.browser-note code {
  font-family: var(--tps-font-mono);
}
</style>
