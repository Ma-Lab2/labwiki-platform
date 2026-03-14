<template>
  <div class="params-form">
    <el-form label-width="70px" size="small">
      <el-form-item label="X0">
        <el-input-number v-model="store.params.X0" :min="0" :max="2000" @change="v => store.updateParam('X0', v)" />
      </el-form-item>
      <el-form-item label="Y0">
        <el-input-number v-model="store.params.Y0" :min="0" :max="2000" @change="v => store.updateParam('Y0', v)" />
      </el-form-item>
      <el-form-item label="±dY">
        <el-input-number v-model="store.params.dY" :min="1" :max="50" @change="v => store.updateParam('dY', v)" />
      </el-form-item>
      <el-form-item label="Emin">
        <el-input-number v-model="store.params.Emin" :min="0" :max="500" :step="0.5" :precision="1" @change="v => store.updateParam('Emin', v)" />
      </el-form-item>
      <el-form-item label="Emax">
        <el-input-number v-model="store.params.Emax" :min="1" :max="500" :step="1" :precision="1" @change="v => store.updateParam('Emax', v)" />
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { useSessionStore } from '../../stores/session'

const store = useSessionStore()
</script>

<style scoped>
.params-form {
  padding: 8px;
}
</style>
