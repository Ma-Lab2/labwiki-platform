<template>
  <div class="app" :data-theme="settings.theme">
    <AppHeader />
    <div class="app-body">
      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="RCF 设计" name="design">
          <div class="design-layout">
            <aside class="left-panel">
              <ParamPanel />
            </aside>
            <main class="center-panel">
              <StackToolbar :selected-index="selectedIndex" />
              <StackTable @select="idx => selectedIndex = idx" />
              <div class="action-bar">
                <el-button type="primary" @click="runCompute" :loading="compute.isComputing">
                  计算
                </el-button>
                <el-radio-group v-model="plotView" size="small">
                  <el-radio-button value="cutoff">截止能量</el-radio-button>
                  <el-radio-button value="deposition">能量沉积</el-radio-button>
                  <el-radio-button value="matrix">响应矩阵</el-radio-button>
                </el-radio-group>
              </div>
              <EnergyCenterPlot v-if="plotView === 'cutoff'" />
              <EnergyDepositionPlot v-if="plotView === 'deposition'" />
              <ResponseMatrixHeatmap v-if="plotView === 'matrix'" />
            </main>
            <aside class="right-panel">
              <MaterialButtons />
            </aside>
          </div>
        </el-tab-pane>
        <el-tab-pane label="线性设计" name="linear">
          <LinearDesignPanel />
        </el-tab-pane>
      </el-tabs>
    </div>
    <ProgressOverlay />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from './stores/settings'
import { useComputeStore } from './stores/compute'
import { useComputation } from './composables/useComputation'
import AppHeader from './components/AppHeader.vue'
import ParamPanel from './components/ParamPanel.vue'
import StackToolbar from './components/StackToolbar.vue'
import StackTable from './components/StackTable.vue'
import MaterialButtons from './components/MaterialButtons.vue'
import EnergyCenterPlot from './components/EnergyCenterPlot.vue'
import EnergyDepositionPlot from './components/EnergyDepositionPlot.vue'
import ResponseMatrixHeatmap from './components/ResponseMatrixHeatmap.vue'
import LinearDesignPanel from './components/LinearDesignPanel.vue'
import ProgressOverlay from './components/ProgressOverlay.vue'

const settings = useSettingsStore()
const compute = useComputeStore()
const { runEnergyScanSync } = useComputation()

const activeTab = ref('design')
const selectedIndex = ref(-1)
const plotView = ref<'cutoff' | 'deposition' | 'matrix'>('cutoff')

async function runCompute() {
  await runEnergyScanSync()
}

onMounted(() => {
  document.documentElement.setAttribute('data-theme', settings.theme)
})
</script>

<style scoped>
.app { min-height: 100vh; display: flex; flex-direction: column; background: var(--rcf-bg); }
.app-body { flex: 1; padding: 0; }
.design-layout { display: flex; gap: 0; min-height: calc(100vh - 120px); }
.left-panel { width: 260px; border-right: 1px solid var(--rcf-border); flex-shrink: 0; background: var(--rcf-bg-card); }
.center-panel { flex: 1; padding: 16px; overflow: auto; background: transparent; }
.right-panel { width: 200px; border-left: 1px solid var(--rcf-border); flex-shrink: 0; background: var(--rcf-bg-card); }
.action-bar { display: flex; align-items: center; gap: 12px; margin: 12px 0; }
</style>
