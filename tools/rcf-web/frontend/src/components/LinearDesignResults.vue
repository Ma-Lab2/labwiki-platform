<template>
  <div v-if="visible" class="linear-results">
    <h3>设计结果</h3>
    <el-table :data="rows" border size="small" style="margin-bottom: 12px">
      <el-table-column prop="index" label="RCF #" width="70" />
      <el-table-column prop="energy" label="截止能量 (MeV)" width="140" />
      <el-table-column prop="alThickness" label="Al 厚度 (μm)" width="140" />
    </el-table>
    <div class="linear-messages">
      <div v-for="(msg, i) in messages" :key="i" class="msg-line">{{ msg }}</div>
    </div>
    <el-button size="small" style="margin-top: 8px" @click="emit('transfer')">转移到主模块</el-button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  rows: Array<{ index: number; energy: string; alThickness: string }>
  messages: string[]
}>()

const emit = defineEmits<{ (e: 'transfer'): void }>()
</script>

<style scoped>
.linear-results { margin-top: 20px; }
.linear-results h3 { margin: 0 0 12px; color: var(--rcf-primary); }
.linear-messages { font-size: 12px; color: #aaa; max-height: 120px; overflow-y: auto; }
.msg-line { padding: 2px 0; }
</style>
