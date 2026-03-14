<template>
  <div class="particle-selector">
    <el-form label-width="50px" size="small">
      <el-form-item label="粒子">
        <el-select v-model="selected" @change="onSelect" style="width: 100%;">
          <el-option v-for="p in store.particles" :key="p.name" :label="p.name" :value="p.name" />
          <el-option label="自定义..." value="custom" />
        </el-select>
      </el-form-item>
      <el-form-item label="A">
        <el-input-number v-model="store.params.A" :min="1" :max="238" :disabled="selected !== 'custom'" @change="v => store.updateParam('A', v)" />
      </el-form-item>
      <el-form-item label="Z">
        <el-input-number v-model="store.params.Z" :min="1" :max="92" :disabled="selected !== 'custom'" @change="v => store.updateParam('Z', v)" />
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useSessionStore } from '../../stores/session'

const store = useSessionStore()
const selected = ref('H-1')

function onSelect(name) {
  if (name === 'custom') return
  store.selectParticle(name)
}
</script>

<style scoped>
.particle-selector {
  padding: 8px;
}
</style>
