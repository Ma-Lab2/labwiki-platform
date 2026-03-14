export default {
  app: { title: 'RCF Stack Spectrometer Design Tool' },
  tabs: { design: 'RCF Design', linear: 'Linear Design' },
  params: {
    title: 'Parameters',
    eMin: 'E_min (MeV)', eMax: 'E_max (MeV)', eStep: 'E_step (MeV)',
    angle: 'Incidence Angle θ (°)', pathFactor: 'Path Factor',
    ion: 'Particle Type',
  },
  stack: {
    material: 'Material', thickness: 'Thickness (μm)', type: 'Type',
    detector: 'Detector', cutoff: 'Cutoff Energy',
    fixed: 'Fixed', variable: 'Variable',
  },
  materials: {
    add: 'Add Material', import: 'Import Material (PSTAR)',
    name: 'Material Name', density: 'Density (g/cm³)',
    selectFile: 'Select File', cancel: 'Cancel', doImport: 'Import',
  },
  compute: { run: 'Compute', computing: 'Computing...', done: 'Done' },
  linear: {
    title: 'Linear Design Parameters',
    alThick1: 'Initial Al Thickness (μm)', interval: 'Energy Interval (MeV)',
    alMin: 'Al Search Min (μm)', alMax: 'Al Search Max (μm)',
    alStep: 'Search Step (μm)', start: 'Start Linear Design',
    result: 'Design Result', transfer: 'Transfer to Main',
    detectors: 'Detector Sequence', clear: 'Clear',
  },
  plots: {
    cutoff: 'Cutoff Energy vs RCF #',
    deposition: 'Energy Deposition Curves',
    matrix: 'Response Matrix',
    linearResult: 'Linear Design Result',
  },
  header: {
    theme: 'Theme', lang: 'Language',
    export: 'Export', exportJson: 'Export JSON', exportMatrix: 'Export Response Matrix',
    importJson: 'Import JSON', importSuccess: 'Import successful',
  },
}
