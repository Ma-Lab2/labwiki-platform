const test = require('node:test');
const assert = require('node:assert/strict');

const {
  detectEditorMode,
  buildDraftHandoffStorageKey,
  matchStructuredFieldsToInventory,
  parseMissingFields
} = require('../modules/ext.labassistant.editor-utils.js');

test('detectEditorMode identifies source edit, PageForms, and VisualEditor contexts', () => {
  assert.equal(
    detectEditorMode({ editorMode: 'source_edit' }),
    'source_edit'
  );
  assert.equal(
    detectEditorMode({ editorMode: 'pageforms_edit' }),
    'pageforms_edit'
  );
  assert.equal(
    detectEditorMode({ editorMode: 'visual_editor' }),
    'visual_editor'
  );
  assert.equal(
    detectEditorMode({ currentAction: 'formedit' }),
    'pageforms_edit'
  );
  assert.equal(
    detectEditorMode({ currentVeAction: 'edit' }),
    'visual_editor'
  );
  assert.equal(
    detectEditorMode({ currentAction: 'edit' }),
    'source_edit'
  );
  assert.equal(
    detectEditorMode({}),
    'default'
  );
});

test('buildDraftHandoffStorageKey scopes the handoff to title and host', () => {
  assert.equal(
    buildDraftHandoffStorageKey('Theory:TNSA', 'localhost:8443'),
    'labassistant-draft-handoff::localhost:8443::Theory:TNSA'
  );
});

test('matchStructuredFieldsToInventory matches conservative aliases for term entry fields', () => {
  const inventory = [
    { key: 'field-cn', label: '中文名', controlType: 'text' },
    { key: 'field-en', label: '英文名', controlType: 'text' },
    { key: 'field-summary', label: '摘要', controlType: 'textarea' },
    { key: 'field-aliases', label: '别名', controlType: 'tokens' },
    { key: 'field-pages', label: '关联页面', controlType: 'tokens' }
  ];
  const suggestions = {
    中文名: 'Rayleigh 长度',
    英文名: 'Rayleigh length',
    摘要: '用于判断焦深和对准容差。',
    别名: '瑞利长度；焦深尺度',
    关联页面: 'Laser:超快激光基础理论；TargetArea:束靶耦合段',
    无关字段: '忽略'
  };

  const matches = matchStructuredFieldsToInventory('术语条目', suggestions, inventory);

  assert.deepEqual(matches, [
    { fieldKey: 'field-cn', fieldLabel: '中文名', suggestionKey: '中文名', value: 'Rayleigh 长度', controlType: 'text', status: 'matched' },
    { fieldKey: 'field-en', fieldLabel: '英文名', suggestionKey: '英文名', value: 'Rayleigh length', controlType: 'text', status: 'matched' },
    { fieldKey: 'field-summary', fieldLabel: '摘要', suggestionKey: '摘要', value: '用于判断焦深和对准容差。', controlType: 'textarea', status: 'matched' },
    { fieldKey: 'field-aliases', fieldLabel: '别名', suggestionKey: '别名', value: [ '瑞利长度', '焦深尺度' ], controlType: 'tokens', status: 'matched' },
    { fieldKey: 'field-pages', fieldLabel: '关联页面', suggestionKey: '关联页面', value: [ 'Laser:超快激光基础理论', 'TargetArea:束靶耦合段' ], controlType: 'tokens', status: 'matched' }
  ]);
});

test('matchStructuredFieldsToInventory matches device entry fields conservatively', () => {
  const inventory = [
    { key: 'device-name', label: '设备名称', controlType: 'text' },
    { key: 'device-system', label: '系统归属', controlType: 'text' },
    { key: 'device-params', label: '关键参数', controlType: 'textarea' },
    { key: 'device-purpose', label: '用途', controlType: 'textarea' },
    { key: 'device-runbook', label: '运行页', controlType: 'tokens' },
    { key: 'device-sources', label: '来源', controlType: 'tokens' }
  ];
  const suggestions = {
    名称: 'TPS',
    归属系统: '主靶室诊断链',
    主要参数: '磁场强度、能区覆盖、狭缝宽度',
    作用: '测量带电粒子能谱并做 shot 后快速判读',
    运行页面: 'Diagnostic:TPS；Control:中央控制平台',
    出处: 'Diagnostic:TPS；首页'
  };

  const matches = matchStructuredFieldsToInventory('设备条目', suggestions, inventory);

  assert.deepEqual(matches, [
    { fieldKey: 'device-name', fieldLabel: '设备名称', suggestionKey: '名称', value: 'TPS', controlType: 'text', status: 'matched' },
    { fieldKey: 'device-system', fieldLabel: '系统归属', suggestionKey: '归属系统', value: '主靶室诊断链', controlType: 'text', status: 'matched' },
    { fieldKey: 'device-params', fieldLabel: '关键参数', suggestionKey: '主要参数', value: '磁场强度、能区覆盖、狭缝宽度', controlType: 'textarea', status: 'matched' },
    { fieldKey: 'device-purpose', fieldLabel: '用途', suggestionKey: '作用', value: '测量带电粒子能谱并做 shot 后快速判读', controlType: 'textarea', status: 'matched' },
    { fieldKey: 'device-runbook', fieldLabel: '运行页', suggestionKey: '运行页面', value: [ 'Diagnostic:TPS', 'Control:中央控制平台' ], controlType: 'tokens', status: 'matched' },
    { fieldKey: 'device-sources', fieldLabel: '来源', suggestionKey: '出处', value: [ 'Diagnostic:TPS', '首页' ], controlType: 'tokens', status: 'matched' }
  ]);
});

test('matchStructuredFieldsToInventory matches diagnostic entry fields conservatively', () => {
  const inventory = [
    { key: 'diag-name', label: '诊断名称', controlType: 'text' },
    { key: 'diag-target', label: '测量对象', controlType: 'text' },
    { key: 'diag-output', label: '主要输出', controlType: 'textarea' },
    { key: 'diag-risks', label: '易错点', controlType: 'textarea' },
    { key: 'diag-tool', label: '工具入口', controlType: 'tokens' },
    { key: 'diag-source', label: '来源', controlType: 'tokens' }
  ];
  const suggestions = {
    名称: 'RCF',
    观测对象: '质子束空间分布与相对能量区间',
    输出: '不同层片的曝光图像与层间响应对比',
    注意事项: '片层顺序、扫描方向和背景扣除容易出错',
    工具页面: 'tools/rcf；Data:实验日志与数据关联',
    参考页面: 'Diagnostic:RCF；Shot:周实验日志'
  };

  const matches = matchStructuredFieldsToInventory('诊断条目', suggestions, inventory);

  assert.deepEqual(matches, [
    { fieldKey: 'diag-name', fieldLabel: '诊断名称', suggestionKey: '名称', value: 'RCF', controlType: 'text', status: 'matched' },
    { fieldKey: 'diag-target', fieldLabel: '测量对象', suggestionKey: '观测对象', value: '质子束空间分布与相对能量区间', controlType: 'text', status: 'matched' },
    { fieldKey: 'diag-output', fieldLabel: '主要输出', suggestionKey: '输出', value: '不同层片的曝光图像与层间响应对比', controlType: 'textarea', status: 'matched' },
    { fieldKey: 'diag-risks', fieldLabel: '易错点', suggestionKey: '注意事项', value: '片层顺序、扫描方向和背景扣除容易出错', controlType: 'textarea', status: 'matched' },
    { fieldKey: 'diag-tool', fieldLabel: '工具入口', suggestionKey: '工具页面', value: [ 'tools/rcf', 'Data:实验日志与数据关联' ], controlType: 'tokens', status: 'matched' },
    { fieldKey: 'diag-source', fieldLabel: '来源', suggestionKey: '参考页面', value: [ 'Diagnostic:RCF', 'Shot:周实验日志' ], controlType: 'tokens', status: 'matched' }
  ]);
});

test('matchStructuredFieldsToInventory matches literature guide fields conservatively', () => {
  const inventory = [
    { key: 'lit-title', label: '标题', controlType: 'text' },
    { key: 'lit-authors', label: '作者', controlType: 'tokens' },
    { key: 'lit-year', label: '年份', controlType: 'text' },
    { key: 'lit-doi', label: 'DOI', controlType: 'text' },
    { key: 'lit-summary', label: '摘要', controlType: 'textarea' },
    { key: 'lit-related', label: '相关页面', controlType: 'tokens' },
    { key: 'lit-source', label: '来源', controlType: 'tokens' }
  ];
  const suggestions = {
    文献标题: 'Target normal sheath acceleration review',
    作者列表: 'A. Macchi；M. Borghesi',
    发表年份: '2013',
    doi: '10.1103/RevModPhys.85.751',
    核心摘要: '综述激光驱动离子加速机制与实验判据。',
    关联页面: 'Theory:TNSA；Theory:激光等离子体加速总览',
    出处: 'OpenAlex；Theory:基础理论总览'
  };

  const matches = matchStructuredFieldsToInventory('文献导读', suggestions, inventory);

  assert.deepEqual(matches, [
    { fieldKey: 'lit-title', fieldLabel: '标题', suggestionKey: '文献标题', value: 'Target normal sheath acceleration review', controlType: 'text', status: 'matched' },
    { fieldKey: 'lit-authors', fieldLabel: '作者', suggestionKey: '作者列表', value: [ 'A. Macchi', 'M. Borghesi' ], controlType: 'tokens', status: 'matched' },
    { fieldKey: 'lit-year', fieldLabel: '年份', suggestionKey: '发表年份', value: '2013', controlType: 'text', status: 'matched' },
    { fieldKey: 'lit-doi', fieldLabel: 'DOI', suggestionKey: 'doi', value: '10.1103/RevModPhys.85.751', controlType: 'text', status: 'matched' },
    { fieldKey: 'lit-summary', fieldLabel: '摘要', suggestionKey: '核心摘要', value: '综述激光驱动离子加速机制与实验判据。', controlType: 'textarea', status: 'matched' },
    { fieldKey: 'lit-related', fieldLabel: '相关页面', suggestionKey: '关联页面', value: [ 'Theory:TNSA', 'Theory:激光等离子体加速总览' ], controlType: 'tokens', status: 'matched' },
    { fieldKey: 'lit-source', fieldLabel: '来源', suggestionKey: '出处', value: [ 'OpenAlex', 'Theory:基础理论总览' ], controlType: 'tokens', status: 'matched' }
  ]);
});

test('matchStructuredFieldsToInventory skips low-confidence placeholder values for autofill', () => {
  const inventory = [
    { key: 'lit-title', label: '标题', controlType: 'text' },
    { key: 'lit-authors', label: '作者', controlType: 'tokens' },
    { key: 'lit-year', label: '年份', controlType: 'text' },
    { key: 'lit-doi', label: 'DOI', controlType: 'text' },
    { key: 'lit-related', label: '相关页面', controlType: 'tokens' },
    { key: 'lit-source', label: '来源', controlType: 'tokens' }
  ];
  const suggestions = {
    标题: 'Playwright 文献导读',
    作者: '无',
    年份: '待补充',
    DOI: '未知',
    相关页面: '文献导读/Playwright文献',
    来源: '表单上下文'
  };

  const matches = matchStructuredFieldsToInventory('文献导读', suggestions, inventory);

  assert.deepEqual(matches, [
    { fieldKey: 'lit-title', fieldLabel: '标题', suggestionKey: '标题', value: 'Playwright 文献导读', controlType: 'text', status: 'matched' },
    { fieldKey: 'lit-related', fieldLabel: '相关页面', suggestionKey: '相关页面', value: [ '文献导读/Playwright文献' ], controlType: 'tokens', status: 'matched' }
  ]);
});

test('parseMissingFields extracts a conservative field list from 缺失字段 lines', () => {
  const missingFields = parseMissingFields([
    '标题：Playwright 文献导读',
    '摘要：面向自动化测试的占位文献导读。',
    '缺失字段：作者；年份；DOI、来源'
  ].join('\n'));

  assert.deepEqual(missingFields, [ '作者', '年份', 'DOI', '来源' ]);
});
