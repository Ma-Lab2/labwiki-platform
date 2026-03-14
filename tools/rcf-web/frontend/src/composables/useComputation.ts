import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useComputeStore } from '../stores/compute'
import { useStackStore } from '../stores/stack'
import { useSettingsStore } from '../stores/settings'
import { energyScan, energyScanAsync } from '../api/compute'
import type { ProgressMessage } from '../types'

const MAX_WS_RETRIES = 5
const BASE_RETRY_DELAY_MS = 500

export function useComputation() {
  const compute = useComputeStore()
  const stack = useStackStore()
  const settings = useSettingsStore()
  const wsRef = ref<WebSocket | null>(null)
  const reconnectTimerRef = ref<number | null>(null)

  function buildWsUrl(taskId: string, token: string) {
    const configuredBase = (import.meta.env.VITE_WS_BASE_URL as string | undefined)?.trim()
    const basePath = import.meta.env.DEV ? '' : '/tools/rcf'

    if (configuredBase) {
      let wsBase = configuredBase.replace(/\/+$/, '')
      if (wsBase.startsWith('http://')) wsBase = `ws://${wsBase.slice('http://'.length)}`
      if (wsBase.startsWith('https://')) wsBase = `wss://${wsBase.slice('https://'.length)}`
      return `${wsBase}${basePath}/api/v1/ws/compute/${taskId}?token=${encodeURIComponent(token)}`
    }

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${location.host}${basePath}/api/v1/ws/compute/${taskId}?token=${encodeURIComponent(token)}`
  }

  async function runEnergyScanSync() {
    compute.startComputing()
    try {
      const result = await energyScan({
        layers: stack.layers,
        energy_min: settings.energyMin,
        energy_max: settings.energyMax,
        energy_step: settings.energyStep,
        incidence_angle: settings.incidenceAngle,
        ion_key: settings.ionKey,
      })
      compute.setEnergyScanResult(result)
    } finally {
      compute.stopComputing()
    }
  }

  async function runEnergyScanAsync() {
    compute.startComputing()
    try {
      const task = await energyScanAsync({
        layers: stack.layers,
        energy_min: settings.energyMin,
        energy_max: settings.energyMax,
        energy_step: settings.energyStep,
        incidence_angle: settings.incidenceAngle,
        ion_key: settings.ionKey,
      })
      connectWs(task.task_id, task.ws_token)
    } catch {
      ElMessage.error('无法启动异步计算，请检查后端服务状态')
      compute.stopComputing()
    }
  }

  function connectWs(taskId: string, token: string, retry = 0) {
    const ws = new WebSocket(buildWsUrl(taskId, token))
    wsRef.value = ws
    let terminalReceived = false

    ws.onmessage = (ev) => {
      const msg: ProgressMessage = JSON.parse(ev.data)
      if (msg.type === 'progress') {
        compute.setProgress(msg.message, msg.percent)
      } else if (msg.type === 'result') {
        terminalReceived = true
        compute.setEnergyScanResult(msg.data)
        compute.stopComputing()
        ws.close()
      } else if (msg.type === 'error') {
        terminalReceived = true
        ElMessage.error(msg.message || '计算过程发生错误')
        compute.stopComputing()
        ws.close()
      }
    }

    ws.onerror = () => {
      if (retry === 0) {
        ElMessage.warning('WebSocket 连接异常，正在尝试重连...')
      }
    }

    ws.onclose = () => {
      wsRef.value = null
      if (terminalReceived || !compute.isComputing) return

      if (retry >= MAX_WS_RETRIES) {
        ElMessage.error('WebSocket 多次重连失败，计算已停止')
        compute.stopComputing()
        return
      }

      const delay = BASE_RETRY_DELAY_MS * 2 ** retry
      reconnectTimerRef.value = window.setTimeout(() => {
        connectWs(taskId, token, retry + 1)
      }, delay)
    }
  }

  function cancelComputation() {
    // Mark stop first so ws.onclose won't trigger reconnect logic.
    compute.stopComputing()

    if (reconnectTimerRef.value) {
      window.clearTimeout(reconnectTimerRef.value)
      reconnectTimerRef.value = null
    }

    if (wsRef.value) {
      wsRef.value.close()
      wsRef.value = null
    }
  }

  return {
    runEnergyScanSync,
    runEnergyScanAsync,
    cancelComputation,
  }
}
