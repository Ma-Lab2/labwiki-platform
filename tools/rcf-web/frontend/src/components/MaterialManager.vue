<template>
  <el-dialog
    :model-value="visible"
    title="导入材料 (PSTAR)"
    width="500px"
    @close="emit('update:visible', false)"
    @update:model-value="(v: boolean) => emit('update:visible', v)"
  >
    <el-form label-width="100px">
      <el-form-item label="材料名称">
        <el-input v-model="name" placeholder="e.g. Mylar" />
      </el-form-item>
      <el-form-item label="密度 (g/cm³)">
        <el-input-number v-model="density" :min="0.001" :max="30" :step="0.01" />
      </el-form-item>
      <el-form-item label="PSTAR CSV">
        <el-upload
          :auto-upload="false"
          :limit="1"
          accept=".csv,.txt"
          @change="handleFileChange"
        >
          <el-button size="small">选择文件</el-button>
        </el-upload>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="replaceExisting">覆盖同名材料</el-checkbox>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="loading" @click="doImport">导入</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { uploadPstar } from '../api/materials'

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'imported'): void
}>()

const name = ref('')
const density = ref(1.0)
const file = ref<File | null>(null)
const loading = ref(false)
const replaceExisting = ref(false)

async function handleFileChange(uploadFile: any) {
  const selected: File | undefined = uploadFile?.raw
  if (!selected) return

  const lower = selected.name.toLowerCase()
  if (!lower.endsWith('.csv') && !lower.endsWith('.txt')) {
    ElMessage.error('仅支持 .csv 或 .txt 文件')
    file.value = null
    return
  }

  try {
    const preview = await selected.slice(0, 2048).text()
    const firstDataLine = preview
      .split(/\r?\n/)
      .map(line => line.trim())
      .find(line => line.length > 0 && !line.startsWith('#') && !line.startsWith('//'))

    if (!firstDataLine || !/[,\s]/.test(firstDataLine)) {
      ElMessage.error('文件格式异常：未检测到有效的 CSV/TXT 数据行')
      file.value = null
      return
    }
  } catch {
    ElMessage.error('文件预检失败，请重试')
    file.value = null
    return
  }

  file.value = selected
}

async function doImport() {
  if (!name.value || !file.value) {
    ElMessage.warning('请填写材料名称并选择文件')
    return
  }
  loading.value = true
  try {
    await uploadPstar(name.value, density.value, file.value, replaceExisting.value)
    ElMessage.success(`材料 ${name.value} 导入成功`)
    emit('imported')
    emit('update:visible', false)
    name.value = ''
    density.value = 1.0
    file.value = null
    replaceExisting.value = false
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '导入失败')
  } finally {
    loading.value = false
  }
}
</script>
