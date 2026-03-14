export default {
  app: { title: 'RCF 叠层谱仪设计工具' },
  tabs: { design: 'RCF 设计', linear: '线性设计' },
  params: {
    title: '参数设置',
    eMin: 'E_min (MeV)', eMax: 'E_max (MeV)', eStep: 'E_step (MeV)',
    angle: '入射角度 θ (°)', pathFactor: '路径因子',
    ion: '粒子类型',
  },
  stack: {
    material: '材料', thickness: '厚度 (μm)', type: '类型',
    detector: '探测器', cutoff: '截止能量',
    fixed: '固定', variable: '可变',
  },
  materials: {
    add: '添加材料', import: '导入材料 (PSTAR)',
    name: '材料名称', density: '密度 (g/cm³)',
    selectFile: '选择文件', cancel: '取消', doImport: '导入',
  },
  compute: { run: '计算', computing: '计算中...', done: '计算完成' },
  linear: {
    title: '线性设计参数',
    alThick1: '初始 Al 厚度 (μm)', interval: '能量间隔 (MeV)',
    alMin: 'Al 搜索最小 (μm)', alMax: 'Al 搜索最大 (μm)',
    alStep: '搜索步长 (μm)', start: '开始线性设计',
    result: '设计结果', transfer: '转移到主模块',
    detectors: '探测器序列', clear: '清空',
  },
  plots: {
    cutoff: '截止能量 vs RCF 编号',
    deposition: '能量沉积曲线',
    matrix: '响应矩阵',
    linearResult: '线性设计结果',
  },
  header: {
    theme: '主题', lang: '语言',
    export: '导出', exportJson: '导出 JSON', exportMatrix: '导出响应矩阵',
    importJson: '导入 JSON', importSuccess: '导入成功',
  },
}
