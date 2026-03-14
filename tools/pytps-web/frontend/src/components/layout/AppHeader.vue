<template>
  <el-header class="app-header">
    <div class="header-brand">
      <div class="brand-mark">TPS</div>
      <div class="brand-copy">
        <p class="eyebrow">实验运行台账 / Diagnostic Workbench</p>
        <h1 class="title">TPS 在线解谱工作台</h1>
        <p class="subtitle">用于汤姆逊抛物谱仪图像浏览、在线解谱、谱线对比与归档回填。</p>
      </div>
    </div>

    <div class="header-actions">
      <div class="header-links">
        <a class="header-link" href="/index.php?title=Diagnostic:TPS">TPS 页面说明</a>
        <a class="header-link" href="/index.php?title=Data:TPS分析与归档">TPS 归档规则</a>
        <a class="header-link" href="/index.php?title=Shot:Shot模板">Shot 模板</a>
      </div>

      <div class="header-toolbar">
        <el-radio-group v-model="sessionStore.mode" size="small">
          <el-radio-button value="offline">离线分析</el-radio-button>
          <el-radio-button value="batch">批处理</el-radio-button>
          <el-radio-button value="online">在线模式</el-radio-button>
        </el-radio-group>

        <div class="header-status">
          <el-tag :type="sessionStore.connected ? 'success' : 'danger'" size="small">
            {{ sessionStore.connected ? '已连接' : '未连接' }}
          </el-tag>
          <el-tag v-if="sessionStore.computing" type="warning" size="small">计算中...</el-tag>
          <el-tag size="small" type="info">会话 {{ sessionStore.sessionId || '初始化中' }}</el-tag>
        </div>
      </div>
    </div>
  </el-header>
</template>

<script setup>
import { useSessionStore } from '../../stores/session'

const sessionStore = useSessionStore()
</script>

<style scoped>
.app-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  min-height: 128px;
  padding: 18px 22px;
  border: 1px solid var(--tps-border-strong);
  border-radius: 24px;
  background:
    linear-gradient(145deg, rgba(249, 252, 251, 0.96), rgba(236, 243, 240, 0.9)),
    var(--tps-panel);
  box-shadow: var(--tps-shadow-card);
}

.header-brand {
  display: flex;
  gap: 16px;
  min-width: 0;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  border-radius: 16px;
  background: var(--tps-primary);
  color: #fff;
  font-family: var(--tps-font-mono);
  font-size: 15px;
  letter-spacing: 0.16em;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.brand-copy {
  min-width: 0;
}

.eyebrow {
  margin: 2px 0 8px;
  color: var(--tps-text-muted);
  font-family: var(--tps-font-mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.title {
  margin: 0;
  color: var(--tps-header-color);
  font-family: var(--tps-font-display);
  font-size: clamp(28px, 2.4vw, 34px);
  font-weight: 600;
  line-height: 1.1;
}

.subtitle {
  margin: 10px 0 0;
  max-width: 640px;
  color: var(--tps-text-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.header-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 14px;
}

.header-links,
.header-toolbar,
.header-status {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.header-link {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 14px;
  border: 1px solid var(--tps-border);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--tps-text-secondary);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  transition: border-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.header-link:hover {
  border-color: var(--tps-primary);
  color: var(--tps-primary);
  transform: translateY(-1px);
}

@media (max-width: 1200px) {
  .app-header {
    flex-direction: column;
  }

  .header-actions {
    align-items: flex-start;
  }

  .header-links,
  .header-toolbar,
  .header-status {
    justify-content: flex-start;
  }
}

@media (max-width: 720px) {
  .app-header {
    padding: 16px;
    border-radius: 20px;
  }

  .brand-mark {
    width: 44px;
    height: 44px;
  }

  .title {
    font-size: 24px;
  }
}
</style>
