import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/index'
import wsClient from '../api/websocket'

export const useSessionStore = defineStore('session', () => {
  const sessionId = ref('')
  const connected = ref(false)
  const computing = ref(false)
  const mode = ref('offline') // offline | online | batch

  const params = reactive({
    X0: 81,
    Y0: 465,
    dY: 3,
    Emin: 0.0,
    Emax: 100.0,
    A: 1,
    Z: 1,
    colormin: 0,
    colormax: 60000,
    specEmin: 0.0,
    specEmax: 100.0,
    specdNdEmin: 1e6,
    specdNdEmax: 3e11,
    filterMode: 'none',
    medianSize: 5,
    medianIterations: 1,
    morphologicalSize: 3,
    rollingBallRadius: 15,
    protectionWidth: 9,
    aggressiveSize: 15,
    gentleSize: 5,
    fadeRadius: 20,
    cmap: 'partical',
    showParabola: false,
  })

  const imagePath = ref('')
  const currentFile = ref('')
  const particles = ref([])
  const colormaps = ref([])

  async function initialize() {
    try {
      // Load init settings
      const initRes = await api.getInitSettings()
      const initData = initRes.data
      Object.keys(initData).forEach(key => {
        if (key in params) {
          params[key] = initData[key]
        }
      })
      imagePath.value = initData.imagePath || '/data/images'

      // Load particles and colormaps
      const [partRes, cmapRes] = await Promise.all([
        api.getParticles(),
        api.getColormaps(),
      ])
      particles.value = partRes.data
      colormaps.value = cmapRes.data

      // Generate session ID and connect WebSocket
      sessionId.value = Math.random().toString(36).substring(2, 10)
      wsClient.connect(sessionId.value)

      wsClient.on('connected', (data) => {
        connected.value = true
        if (data.params) {
          Object.keys(data.params).forEach(key => {
            if (key in params) params[key] = data.params[key]
          })
        }
      })

      wsClient.on('computing', (data) => {
        computing.value = data.status === 'started'
      })

      wsClient.on('error_msg', (data) => {
        ElMessage.error(data.message || '服务器错误')
      })

      wsClient.on('close', () => {
        connected.value = false
      })
    } catch (e) {
      console.error('Failed to initialize:', e)
      ElMessage.error('初始化失败，请检查后端服务是否启动')
    }
  }

  function updateParam(param, value) {
    params[param] = value
    wsClient.updateParam(param, value)
  }

  function updateParams(updates) {
    Object.assign(params, updates)
    wsClient.updateParams(updates)
  }

  function selectParticle(name) {
    const p = particles.value.find(x => x.name === name)
    if (p) {
      params.A = p.A
      params.Z = p.Z
      wsClient.updateParams({ A: p.A, Z: p.Z })
    }
  }

  return {
    sessionId, connected, computing, mode,
    params, imagePath, currentFile, particles, colormaps,
    initialize, updateParam, updateParams, selectParticle,
  }
})
