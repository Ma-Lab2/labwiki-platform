<template>
  <div class="material-buttons">
    <h3>添加材料</h3>
    <div class="btn-grid">
      <el-button @click="addMaterial('Al', 30, false)">Al</el-button>
      <el-button @click="addMaterial('Cu', 10, true)">Cu</el-button>
      <el-button @click="addMaterial('Cr', 10, true)">Cr</el-button>
      <el-button type="primary" @click="addMaterial('HD', 105, true)">HD</el-button>
      <el-button type="success" @click="addMaterial('EBT', 280, true)">EBT</el-button>
    </div>
    <el-divider />
    <h4>自定义材料</h4>
    <div class="btn-grid">
      <el-button
        v-for="mat in customMaterials"
        :key="mat.name"
        size="small"
        @click="addMaterial(mat.name, 100, false)"
      >
        {{ mat.name }}
      </el-button>
    </div>
    <el-button size="small" style="margin-top: 8px" @click="showImport = true">
      导入材料 (PSTAR)
    </el-button>
    <MaterialManager v-model:visible="showImport" @imported="refreshMaterials" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useStackStore } from '../stores/stack'
import { getMaterials } from '../api/materials'
import type { MaterialInfo } from '../types'
import MaterialManager from './MaterialManager.vue'

const stack = useStackStore()
const customMaterials = ref<MaterialInfo[]>([])
const showImport = ref(false)

function addMaterial(name: string, thickness: number, isDetector: boolean) {
  const thicknessType = isDetector ? 'fixed' : 'variable'
  stack.addLayer({ material_name: name, thickness, thickness_type: thicknessType, is_detector: isDetector })
}

async function refreshMaterials() {
  try {
    const all = await getMaterials()
    customMaterials.value = all.filter(m => !['Al', 'Cu', 'Cr', 'HD', 'EBT'].includes(m.name))
  } catch {
    ElMessage.error('加载材料列表失败，请检查后端连接')
  }
}

onMounted(refreshMaterials)
</script>

<style scoped>
.material-buttons { padding: 16px 18px 18px; }
.material-buttons h3 {
  margin: 0 0 10px;
  color: var(--rcf-primary-strong);
  font-family: var(--rcf-font-mono);
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.material-buttons h4 {
  margin: 0 0 8px;
  color: var(--rcf-text-secondary);
  font-family: var(--rcf-font-mono);
  font-size: 11px;
}
.btn-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.btn-grid .el-button {
  min-width: 66px;
  font-size: 12px;
}
</style>
