/** Stack layer definition */
export interface StackLayer {
  material_name: string
  thickness: number
  thickness_type: 'variable' | 'fixed'
  is_detector: boolean
  layer_id?: string
}

/** Material info from backend */
export interface MaterialInfo {
  name: string
  density: number
  source: 'builtin' | 'pstar' | 'upload'
  csv_path?: string
}

/** Single RCF detector result */
export interface RCFResult {
  rcf_id: number
  name: string
  table_id: number
  layer_id?: string
  cutoff_energy: number | null
  energy_zoom: number[]
  edep_curve_x: number[]
  edep_curve_y: number[]
}

/** Energy scan response */
export interface EnergyScanResponse {
  rcf_results: RCFResult[]
  res_ene_matrix: number[][]
  energy_range: number[]
}

/** Energy scan request */
export interface EnergyScanRequest {
  layers: StackLayer[]
  energy_min: number
  energy_max: number
  energy_step: number
  incidence_angle: number
  ion_key: string
}

/** Linear design request */
export interface LinearDesignRequest {
  detectors: StackLayer[]
  al_thick_1: number
  energy_interval: number
  al_thick_min: number
  al_thick_max: number
  al_interval: number
  incidence_angle: number
}

/** Linear design response */
export interface LinearDesignResponse {
  energy_sequence: number[]
  al_thickness_sequence: number[]
  full_stack: StackLayer[]
  messages: string[]
}

/** WebSocket progress message */
export interface ProgressMessage {
  type: 'progress' | 'result' | 'error'
  message: string
  percent: number
  data?: any
}

/** Async computation task bootstrap response */
export interface AsyncTaskResponse {
  task_id: string
  ws_token: string
  expires_at: string
}

/** Ion option for selector */
export interface IonOption {
  label: string
  value: string
}

/** Available ions */
export const ION_OPTIONS: IonOption[] = [
  { label: '质子 (proton)', value: 'proton' },
  { label: '氘核 (deuteron)', value: 'deuteron' },
  { label: 'α粒子 (He4)', value: 'He4' },
  { label: '碳-12 (C12)', value: 'C12' },
  { label: '氮-14 (N14)', value: 'N14' },
  { label: '氧-16 (O16)', value: 'O16' },
  { label: '氖-20 (Ne20)', value: 'Ne20' },
  { label: '硅-28 (Si28)', value: 'Si28' },
  { label: '氩-40 (Ar40)', value: 'Ar40' },
  { label: '铁-56 (Fe56)', value: 'Fe56' },
]
