<template>
  <div class="display-params">
    <el-form label-width="80px" size="small">
      <el-form-item label="色标最小">
        <el-input-number v-model="store.params.colormin" :min="0" :max="65535" :step="100" @change="v => store.updateParam('colormin', v)" />
      </el-form-item>
      <el-form-item label="色标最大">
        <el-input-number v-model="store.params.colormax" :min="1" :max="65535" :step="1000" @change="v => store.updateParam('colormax', v)" />
      </el-form-item>
      <el-form-item label="色表">
        <el-select v-model="store.params.cmap" @change="v => store.updateParam('cmap', v)" style="width: 100%;">
          <el-option v-for="cm in store.colormaps" :key="cm" :label="cm" :value="cm" />
        </el-select>
      </el-form-item>
      <el-form-item label="谱E最小">
        <el-input-number v-model="store.params.specEmin" :min="0" :max="500" :step="1" :precision="1" @change="v => store.updateParam('specEmin', v)" />
      </el-form-item>
      <el-form-item label="谱E最大">
        <el-input-number v-model="store.params.specEmax" :min="1" :max="500" :step="5" :precision="1" @change="v => store.updateParam('specEmax', v)" />
      </el-form-item>
      <el-form-item label="dN/dE最小">
        <el-input-number v-model="store.params.specdNdEmin" :min="1" :step="1e6" @change="v => store.updateParam('specdNdEmin', v)" />
      </el-form-item>
      <el-form-item label="dN/dE最大">
        <el-input-number v-model="store.params.specdNdEmax" :min="1" :step="1e9" @change="v => store.updateParam('specdNdEmax', v)" />
      </el-form-item>
      <el-form-item label="抛物线">
        <el-switch v-model="store.params.showParabola" @change="v => { store.updateParam('showParabola', v); toggleParabola(v) }" />
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { useSessionStore } from '../../stores/session'
import wsClient from '../../api/websocket'

const store = useSessionStore()

function toggleParabola(show) {
  wsClient.toggleParabola(show)
}
</script>

<style scoped>
.display-params {
  padding: 8px;
}
</style>
