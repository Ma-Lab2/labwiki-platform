<template>
  <div class="filter-settings">
    <el-form label-width="80px" size="small">
      <el-form-item label="滤波模式">
        <el-select v-model="store.params.filterMode" @change="applyFilter" style="width: 100%;">
          <el-option label="无滤波" value="none" />
          <el-option label="中值滤波" value="median" />
          <el-option label="形态学" value="morphological" />
          <el-option label="滚球法" value="rolling_ball" />
          <el-option label="形态学分割" value="protected" />
          <el-option label="软掩膜" value="soft_mask" />
        </el-select>
      </el-form-item>

      <template v-if="store.params.filterMode === 'median' || store.params.filterMode === 'rolling_ball'">
        <el-form-item label="窗口大小">
          <el-input-number v-model="store.params.medianSize" :min="3" :max="15" :step="2" @change="applyFilter" />
        </el-form-item>
        <el-form-item label="迭代次数">
          <el-input-number v-model="store.params.medianIterations" :min="1" :max="5" @change="applyFilter" />
        </el-form-item>
      </template>

      <template v-if="store.params.filterMode === 'morphological'">
        <el-form-item label="结构元素">
          <el-input-number v-model="store.params.morphologicalSize" :min="3" :max="7" :step="2" @change="applyFilter" />
        </el-form-item>
      </template>

      <template v-if="store.params.filterMode === 'rolling_ball'">
        <el-form-item label="滚球半径">
          <el-input-number v-model="store.params.rollingBallRadius" :min="5" :max="50" @change="applyFilter" />
        </el-form-item>
      </template>

      <template v-if="store.params.filterMode === 'soft_mask'">
        <el-form-item label="羽化半径">
          <el-input-number v-model="store.params.fadeRadius" :min="10" :max="50" @change="applyFilter" />
        </el-form-item>
      </template>
    </el-form>
  </div>
</template>

<script setup>
import { useSessionStore } from '../../stores/session'
import wsClient from '../../api/websocket'

const store = useSessionStore()

function applyFilter() {
  wsClient.applyFilter(store.params.filterMode, {
    medianSize: store.params.medianSize,
    medianIterations: store.params.medianIterations,
    morphologicalSize: store.params.morphologicalSize,
    rollingBallRadius: store.params.rollingBallRadius,
    fadeRadius: store.params.fadeRadius,
    protectionWidth: store.params.protectionWidth,
  })
}
</script>

<style scoped>
.filter-settings {
  padding: 8px;
}
</style>
