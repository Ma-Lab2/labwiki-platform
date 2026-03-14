<template>
  <div class="app-header">
    <h1>{{ t.app.title }}</h1>
    <div class="header-controls">
      <el-select v-model="settings.theme" size="small" style="width: 140px" @change="applyTheme">
        <el-option label="Electric Blue" value="electric-blue" />
        <el-option label="Matrix Green" value="matrix-green" />
        <el-option label="Red Alert" value="red-alert" />
        <el-option label="Clean Light" value="clean-light" />
      </el-select>
      <el-select v-model="settings.locale" size="small" style="width: 90px">
        <el-option label="中文" value="zh-CN" />
        <el-option label="EN" value="en-US" />
      </el-select>
      <el-button size="small" @click="triggerImport">{{ t.header.importJson }}</el-button>
      <input ref="fileInput" type="file" accept=".json" style="display:none" @change="handleImport" />
      <el-dropdown trigger="click">
        <el-button size="small">{{ t.header.export }}</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item @click="exportJson">{{ t.header.exportJson }}</el-dropdown-item>
            <el-dropdown-item @click="exportMatrix">{{ t.header.exportMatrix }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useSettingsStore } from '../stores/settings'
import { useStackStore } from '../stores/stack'
import { useComputeStore } from '../stores/compute'
import { useLocale } from '../composables/useLocale'
import { importStackJson } from '../api/materials'

const settings = useSettingsStore()
const stack = useStackStore()
const compute = useComputeStore()
const { t } = useLocale()
const fileInput = ref<HTMLInputElement | null>(null)

function applyTheme(theme: string) {
  document.documentElement.setAttribute('data-theme', theme)
}

function triggerImport() {
  fileInput.value?.click()
}

async function handleImport(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    const result = await importStackJson(file)
    stack.importFromJson(result.layers)
    ElMessage.success(t.value.header.importSuccess ?? '导入成功')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '导入失败')
  }
  input.value = ''
}

function exportJson() {
  const data = stack.exportToJson()
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'rcf_stack.json'
  a.click()
  URL.revokeObjectURL(url)
}

function exportMatrix() {
  if (compute.resEneMatrix.length === 0) return
  const lines = compute.resEneMatrix.map(row => row.map(v => v.toFixed(6)).join(' '))
  const blob = new Blob([lines.join('\n')], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'response_matrix.txt'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 2px solid var(--rcf-border-strong);
  background: var(--rcf-bg-secondary);
}
.app-header h1 {
  font-size: 18px;
  color: var(--rcf-primary);
  font-weight: 600;
  font-family: var(--rcf-font-mono);
  text-shadow: var(--rcf-glow);
}
.header-controls {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
