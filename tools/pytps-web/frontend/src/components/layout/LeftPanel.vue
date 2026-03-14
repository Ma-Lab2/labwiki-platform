<template>
  <el-aside width="340px" class="left-panel">
    <el-scrollbar>
      <el-collapse v-model="activeCollapse">
        <!-- File Browser -->
        <el-collapse-item title="文件列表" name="files">
          <DirectoryBrowser />
          <FileList />
        </el-collapse-item>

        <!-- Analysis Parameters -->
        <el-collapse-item title="分析参数" name="params">
          <AnalysisParams />
        </el-collapse-item>

        <!-- Particle Selector -->
        <el-collapse-item title="粒子选择" name="particle">
          <ParticleSelector />
        </el-collapse-item>

        <!-- Filter Settings -->
        <el-collapse-item title="滤波设置" name="filter">
          <FilterSettings />
        </el-collapse-item>

        <!-- Display Parameters -->
        <el-collapse-item title="显示设置" name="display">
          <DisplayParams />
        </el-collapse-item>

        <!-- TPS Hardware Settings -->
        <el-collapse-item title="TPS硬件参数" name="tps">
          <TPSSettings />
        </el-collapse-item>
      </el-collapse>
    </el-scrollbar>
  </el-aside>
</template>

<script setup>
import { ref } from 'vue'
import DirectoryBrowser from '../file/DirectoryBrowser.vue'
import FileList from '../file/FileList.vue'
import AnalysisParams from '../settings/AnalysisParams.vue'
import ParticleSelector from '../settings/ParticleSelector.vue'
import FilterSettings from '../settings/FilterSettings.vue'
import DisplayParams from '../settings/DisplayParams.vue'
import TPSSettings from '../settings/TPSSettings.vue'

const activeCollapse = ref(['files', 'params'])
</script>

<style scoped>
.left-panel {
  border: 1px solid var(--tps-border);
  border-radius: 22px;
  background: var(--tps-panel-strong);
  box-shadow: var(--tps-shadow-card);
  overflow: hidden;
}
</style>
