/**
 * WebSocket client with auto-reconnect, message queue, and message dispatch.
 */

class WebSocketClient {
  constructor() {
    this.ws = null
    this.sessionId = null
    this.handlers = {}
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 10
    this.reconnectDelay = 1000
    this.pendingMessages = []
    this._connectPromise = null
  }

  connect(sessionId) {
    this.sessionId = sessionId
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const basePath = import.meta.env.DEV ? '' : '/tools/tps'
    const url = `${protocol}//${host}${basePath}/ws/${sessionId}`

    this._connectPromise = new Promise((resolve, reject) => {
      this.ws = new WebSocket(url)

      this.ws.onopen = () => {
        console.log('[WS] Connected:', sessionId)
        this.reconnectAttempts = 0
        this._emit('open')
        resolve()

        // Flush pending messages
        while (this.pendingMessages.length > 0) {
          const msg = this.pendingMessages.shift()
          console.log('[WS] Sending queued message:', msg.type)
          this.ws.send(JSON.stringify(msg))
        }
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          this._emit(data.type, data)
          this._emit('message', data)
        } catch (e) {
          console.error('[WS] Parse error:', e)
        }
      }

      this.ws.onclose = () => {
        console.log('[WS] Disconnected')
        this._emit('close')
        this._tryReconnect()
      }

      this.ws.onerror = (err) => {
        console.error('[WS] Error:', err)
        this._emit('error', err)
        reject(err)
      }
    })

    return this._connectPromise
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    } else {
      console.warn('[WS] Not connected, queuing message:', data.type)
      this.pendingMessages.push(data)
    }
  }

  selectImage(path) {
    this.send({ type: 'select_image', path })
  }

  updateParam(param, value) {
    this.send({ type: 'update_param', param, value })
  }

  updateParams(params) {
    this.send({ type: 'update_params', params })
  }

  setCursor(energy) {
    this.send({ type: 'set_cursor', energy })
  }

  toggleParabola(show) {
    this.send({ type: 'toggle_parabola', show })
  }

  applyFilter(mode, params) {
    this.send({ type: 'apply_filter', mode, params })
  }

  startWatch(directory) {
    this.send({ type: 'start_watch', directory })
  }

  stopWatch() {
    this.send({ type: 'stop_watch' })
  }

  batchAnalyze(filePaths) {
    this.send({ type: 'batch_analyze', file_paths: filePaths })
  }

  compare(filePaths, options = {}) {
    this.send({ type: 'compare', file_paths: filePaths, ...options })
  }

  fit(EfitMin, EfitMax) {
    this.send({ type: 'fit', Efit_min: EfitMin, Efit_max: EfitMax })
  }

  exportSpectrum() {
    this.send({ type: 'export_spectrum' })
  }

  on(event, handler) {
    if (!this.handlers[event]) this.handlers[event] = []
    this.handlers[event].push(handler)
  }

  off(event, handler) {
    if (this.handlers[event]) {
      this.handlers[event] = this.handlers[event].filter(h => h !== handler)
    }
  }

  _emit(event, data) {
    if (this.handlers[event]) {
      this.handlers[event].forEach(h => h(data))
    }
  }

  _tryReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1)
      console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`)
      setTimeout(() => this.connect(this.sessionId), delay)
    }
  }

  disconnect() {
    this.maxReconnectAttempts = 0
    this.pendingMessages = []
    if (this.ws) this.ws.close()
  }
}

export const wsClient = new WebSocketClient()
export default wsClient
