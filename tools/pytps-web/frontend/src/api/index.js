import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.DEV ? '/api' : '/tools/tps/api',
  timeout: 60000,
})

export default {
  // Files
  listFiles(path) {
    return api.get('/files/list', { params: { path } })
  },
  browseDirectory(path) {
    return api.get('/files/browse', { params: { path } })
  },
  uploadFile(file, path) {
    const form = new FormData()
    form.append('file', file)
    return api.post('/files/upload', form, { params: { path } })
  },

  // Settings
  getTPSSettings() {
    return api.get('/settings/tps')
  },
  updateTPSSettings(settings) {
    return api.put('/settings/tps', settings)
  },
  getInitSettings() {
    return api.get('/settings/init')
  },
  getParticles() {
    return api.get('/settings/particles')
  },
  getColormaps() {
    return api.get('/settings/colormaps')
  },

  // Analysis (REST fallback)
  solveImage(imagePath, params) {
    return api.post('/analysis/solve', { image_path: imagePath, params })
  },
  batchAnalysis(filePaths, params) {
    return api.post('/analysis/batch', { file_paths: filePaths, params })
  },
  compareProtons(filePaths, options) {
    return api.post('/analysis/compare', { file_paths: filePaths, ...options })
  },

  // Health
  health() {
    return api.get('/health')
  },
}
