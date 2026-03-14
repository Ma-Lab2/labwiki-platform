<template>
  <div class="app" :data-theme="settings.theme">
    <AppHeader />
    <div class="app-body">
      <section class="app-intro">
        <div class="intro-copy">
          <small>{{ t.intro.kicker }}</small>
          <h2>{{ t.intro.title }}</h2>
          <p>{{ t.intro.summary }}</p>
        </div>
        <div class="intro-steps">
          <div class="intro-step">
            <span>01</span>
            <p>{{ t.intro.step1 }}</p>
          </div>
          <div class="intro-step">
            <span>02</span>
            <p>{{ t.intro.step2 }}</p>
          </div>
          <div class="intro-step">
            <span>03</span>
            <p>{{ t.intro.step3 }}</p>
          </div>
        </div>
      </section>

      <section class="workspace-shell">
      <el-tabs v-model="activeTab" type="border-card" class="workspace-tabs">
        <el-tab-pane :label="t.tabs.design" name="design">
          <div class="design-layout">
            <aside class="panel-shell left-panel">
              <div class="panel-head">
                <small>{{ t.sections.inputKicker }}</small>
                <strong>{{ t.sections.inputTitle }}</strong>
              </div>
              <ParamPanel />
            </aside>
            <main class="center-panel">
              <div class="section-head">
                <div>
                  <small>{{ t.sections.designKicker }}</small>
                  <strong>{{ t.sections.designTitle }}</strong>
                </div>
                <p>{{ t.sections.designSummary }}</p>
              </div>
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
              <div class="chart-shell">
                <EnergyCenterPlot v-if="plotView === 'cutoff'" />
                <EnergyDepositionPlot v-if="plotView === 'deposition'" />
                <ResponseMatrixHeatmap v-if="plotView === 'matrix'" />
              </div>
              <div class="archive-note">{{ t.sections.archiveNote }}</div>
            </main>
            <aside class="panel-shell right-panel">
              <div class="panel-head">
                <small>{{ t.sections.materialKicker }}</small>
                <strong>{{ t.sections.materialTitle }}</strong>
              </div>
              <MaterialButtons />
            </aside>
          </div>
        </el-tab-pane>
        <el-tab-pane :label="t.tabs.linear" name="linear">
          <div class="linear-shell">
            <div class="section-head">
              <div>
                <small>{{ t.sections.linearKicker }}</small>
                <strong>{{ t.sections.linearTitle }}</strong>
              </div>
              <p>{{ t.sections.linearSummary }}</p>
            </div>
            <LinearDesignPanel />
          </div>
        </el-tab-pane>
      </el-tabs>
      </section>
    </div>
    <ProgressOverlay />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSettingsStore } from './stores/settings'
import { useComputeStore } from './stores/compute'
import { useComputation } from './composables/useComputation'
import { useLocale } from './composables/useLocale'
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
const { t } = useLocale()

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
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-body {
  flex: 1;
  padding: 22px 24px 28px;
}

.app-intro {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.9fr);
  gap: 18px;
  margin-bottom: 18px;
}

.intro-copy,
.intro-steps {
  border: 1px solid var(--rcf-border);
  border-radius: var(--rcf-radius-lg);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.46), rgba(255, 255, 255, 0)),
    rgba(251, 253, 252, 0.8);
  box-shadow: var(--rcf-shadow-card);
}

.intro-copy {
  padding: 24px 26px;
}

.intro-copy small,
.section-head small,
.panel-head small {
  display: block;
  margin-bottom: 8px;
  color: var(--rcf-text-secondary);
  font-family: var(--rcf-font-mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.intro-copy h2 {
  margin-bottom: 10px;
  color: var(--rcf-primary-strong);
  font-family: var(--rcf-font-display);
  font-size: clamp(1.45rem, 2.8vw, 2rem);
  line-height: 1.1;
}

.intro-copy p,
.section-head p,
.archive-note {
  color: var(--rcf-text-secondary);
  line-height: 1.7;
}

.intro-steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  padding: 18px;
}

.intro-step {
  min-height: 118px;
  padding: 18px 16px;
  border-radius: 18px;
  background: rgba(245, 249, 248, 0.8);
  border: 1px solid rgba(183, 200, 195, 0.56);
}

.intro-step span {
  display: inline-flex;
  margin-bottom: 16px;
  color: var(--rcf-primary);
  font-family: var(--rcf-font-mono);
  font-size: 12px;
  letter-spacing: 0.12em;
}

.intro-step p {
  color: var(--rcf-text);
  line-height: 1.6;
}

.workspace-shell {
  padding: 20px 22px 22px;
  border: 1px solid var(--rcf-border);
  border-radius: 28px;
  background: rgba(251, 253, 252, 0.82);
  box-shadow: var(--rcf-shadow-soft);
}

.design-layout {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 250px;
  gap: 18px;
  align-items: start;
}

.panel-shell,
.chart-shell,
.linear-shell {
  border: 1px solid var(--rcf-border);
  border-radius: var(--rcf-radius-md);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.48), rgba(255, 255, 255, 0)),
    rgba(251, 253, 252, 0.74);
  box-shadow: var(--rcf-shadow-card);
}

.left-panel,
.right-panel {
  min-height: 100%;
}

.panel-head,
.section-head {
  padding-bottom: 12px;
  border-bottom: 1px solid var(--rcf-border);
}

.panel-head {
  padding: 18px 18px 12px;
}

.panel-head strong,
.section-head strong {
  display: block;
  color: var(--rcf-primary-strong);
  font-family: var(--rcf-font-display);
  font-size: 1.15rem;
}

.center-panel {
  min-width: 0;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: end;
  margin-bottom: 14px;
}

.section-head p {
  max-width: 42ch;
  text-align: right;
}

.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 14px 0;
  flex-wrap: wrap;
}

.chart-shell {
  padding: 12px;
}

.archive-note {
  margin-top: 14px;
  padding: 14px 16px;
  border-left: 4px solid var(--rcf-secondary);
  border-radius: 14px;
  background: rgba(122, 92, 63, 0.08);
}

.linear-shell {
  padding: 18px;
}

@media (max-width: 1180px) {
  .design-layout {
    grid-template-columns: 280px minmax(0, 1fr);
  }

  .right-panel {
    grid-column: 1 / -1;
  }
}

@media (max-width: 900px) {
  .app-body {
    padding: 16px;
  }

  .app-intro,
  .design-layout {
    grid-template-columns: 1fr;
  }

  .intro-steps {
    grid-template-columns: 1fr;
  }

  .workspace-shell {
    padding: 16px;
    border-radius: 22px;
  }

  .section-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .section-head p {
    text-align: left;
  }
}
</style>
