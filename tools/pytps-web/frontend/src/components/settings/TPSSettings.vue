<template>
  <div class="tps-settings">
    <el-form label-width="60px" size="small" v-if="loaded">
      <el-form-item v-for="(val, key) in tpsParams" :key="key" :label="key">
        <el-input-number v-model="tpsParams[key]" :precision="6" :step="getStep(key)" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" size="small" @click="save">保存TPS参数</el-button>
      </el-form-item>
    </el-form>
    <el-skeleton v-else :rows="8" animated />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../../api/index'

const loaded = ref(false)
const tpsParams = reactive({})

onMounted(async () => {
  try {
    const res = await api.getTPSSettings()
    Object.assign(tpsParams, res.data)
    loaded.value = true
  } catch (e) {
    console.error('Failed to load TPS settings:', e)
  }
})

function getStep(key) {
  const steps = { B: 0.01, U: 100, EMGain: 10, S1: 0.1, Res: 0.001, QE: 0.01 }
  return steps[key] || 1
}

async function save() {
  try {
    await api.updateTPSSettings(tpsParams)
    ElMessage.success('TPS参数已保存')
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  }
}
</script>

<style scoped>
.tps-settings {
  padding: 8px;
}
</style>
