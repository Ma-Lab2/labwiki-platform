<template>
  <el-container class="app-shell">
    <AppHeader />
    <el-container class="workspace">
      <LeftPanel />
      <RightPanel />
    </el-container>
  </el-container>
</template>

<script setup>
import AppHeader from './components/layout/AppHeader.vue'
import LeftPanel from './components/layout/LeftPanel.vue'
import RightPanel from './components/layout/RightPanel.vue'
import { useSessionStore } from './stores/session'
import { onMounted } from 'vue'

const sessionStore = useSessionStore()

onMounted(() => {
  sessionStore.initialize()
})
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  flex-direction: column;
  padding: 16px;
  gap: 14px;
}

.workspace {
  flex: 1;
  min-height: 0;
  gap: 14px;
}
</style>
