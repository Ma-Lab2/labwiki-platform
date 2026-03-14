<template>
  <div class="app-header">
    <div class="header-brand">
      <small>{{ t.intro.kicker }}</small>
      <div class="header-title-row">
        <h1>{{ t.app.title }}</h1>
        <span class="header-badge">{{ t.header.badge }}</span>
      </div>
      <p>{{ t.header.summary }}</p>
    </div>
    <div class="header-actions">
      <div class="header-links">
        <a class="header-link" href="/index.php?title=Diagnostic:RCF">{{ t.header.reference }}</a>
        <a class="header-link" href="/index.php?title=Data:RCF计算与归档">{{ t.header.archive }}</a>
        <a class="header-link" href="/">{{ t.header.backToWiki }}</a>
      </div>
      <div class="header-controls">
        <el-select v-model="settings.locale" size="small" style="width: 96px">
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
  a.download = 'rcf-input-snapshot.json'
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
  a.download = 'rcf-response-matrix.txt'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.app-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 24px 28px 18px;
  border-bottom: 1px solid var(--rcf-border);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.56), rgba(255, 255, 255, 0)),
    rgba(251, 253, 252, 0.72);
}

.header-brand {
  max-width: 760px;
}

.header-brand small {
  display: block;
  margin-bottom: 8px;
  color: var(--rcf-text-secondary);
  font-family: var(--rcf-font-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.header-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.app-header h1 {
  font-size: clamp(1.7rem, 3vw, 2.25rem);
  color: var(--rcf-primary-strong);
  font-weight: 700;
  font-family: var(--rcf-font-display);
  line-height: 1.05;
}

.header-badge {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(32, 85, 102, 0.08);
  color: var(--rcf-primary);
  font-family: var(--rcf-font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.header-brand p {
  max-width: 58ch;
  margin-top: 10px;
  color: var(--rcf-text-secondary);
  line-height: 1.6;
}

.header-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
}

.header-links {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.header-link {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid var(--rcf-border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.58);
  color: var(--rcf-text-secondary);
  font-size: 0.92rem;
  text-decoration: none;
  transition: border-color 140ms ease, color 140ms ease, background-color 140ms ease, transform 140ms ease;
}

.header-link:hover {
  border-color: var(--rcf-primary);
  background: rgba(255, 255, 255, 0.84);
  color: var(--rcf-primary);
  transform: translateY(-1px);
}

.header-controls {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

@media (max-width: 960px) {
  .app-header,
  .header-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions,
  .header-links,
  .header-controls {
    justify-content: flex-start;
    align-items: flex-start;
  }
}
</style>
