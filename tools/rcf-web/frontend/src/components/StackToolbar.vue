<template>
  <div class="stack-toolbar">
    <el-button size="small" @click="stack.moveUp(selectedIndex)" :disabled="selectedIndex <= 0">↑</el-button>
    <el-button size="small" @click="stack.moveDown(selectedIndex)" :disabled="selectedIndex >= stack.layers.length - 1">↓</el-button>
    <el-button size="small" type="danger" @click="stack.removeLayer(selectedIndex)" :disabled="selectedIndex < 0">×</el-button>
    <el-button size="small" @click="stack.clearAll()">清空</el-button>
  </div>
</template>

<script setup lang="ts">
import { useStackStore } from '../stores/stack'
const stack = useStackStore()
defineProps<{ selectedIndex: number }>()
</script>

<style scoped>
.stack-toolbar { display: flex; gap: 4px; margin-bottom: 8px; }
</style>
