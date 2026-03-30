const test = require('node:test');
const assert = require('node:assert/strict');

const {
  detectEditorMode,
  buildDraftHandoffStorageKey,
  buildSubmissionGuidanceStorageKey,
  buildFormFillNotice,
  buildSubmissionChecklistSections,
  buildResultFillFieldSections,
  buildSubmissionChecklistNotice,
  matchStructuredFieldsToInventory,
  normalizeMissingItemEntries,
  parseMissingFields,
  replaceManagedPageSectionBody,
  resolvePageFormRuntimeContext
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

test('buildSubmissionGuidanceStorageKey scopes submission guidance to title and host', () => {
  assert.equal(
    buildSubmissionGuidanceStorageKey('Shot:2026-03-23-Run96-Shot001', 'localhost:8443'),
    'labassistant-submission-guidance::localhost:8443::Shot:2026-03-23-Run96-Shot001'
  );
});

test('replaceManagedPageSectionBody replaces only the target managed section body', () => {
  const source = [
    '<!-- LABWIKI_MANAGED_PAGE:PRIVATE_SHOT_INDEX -->',
    '= Shot:Shot日志入口 =',
    '',
    '== 使用规则 ==',
    '* 每轮实验 / 每个 shot 一页',
    '* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`',
    '',
    '== 必填页面 ==',
    '* [[Shot:表单新建]]'
  ].join('\n');

  const output = replaceManagedPageSectionBody(
    source,
    '使用规则',
    [
      '* 每轮实验 / 每个 shot 一页',
      '* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`',
      '* 每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径'
    ]
  );

  assert.match(output, /== 使用规则 ==\n\* 每轮实验 \/ 每个 shot 一页\n\* 页面命名：`Shot:YYYY-MM-DD-RunXX-ShotYYY`\n\* 每个 Shot 页面必须备注原日志存放位置，包括实验室电脑名称（或编号）与文件夹完整路径\n\n== 必填页面 ==/);
  assert.match(output, /== 必填页面 ==\n\* \[\[Shot:表单新建\]\]/);
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
    { key: 'lit-pdf', label: 'PDF文件', controlType: 'text' },
    { key: 'lit-summary', label: '摘要', controlType: 'textarea' },
    { key: 'lit-related', label: '相关页面', controlType: 'tokens' },
    { key: 'lit-source', label: '来源', controlType: 'tokens' }
  ];
  const suggestions = {
    文献标题: 'Target normal sheath acceleration review',
    作者列表: 'A. Macchi；M. Borghesi',
    发表年份: '2013',
    doi: '10.1103/RevModPhys.85.751',
    PDF文件: 'File:Macchi2013.pdf',
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
    { fieldKey: 'lit-pdf', fieldLabel: 'PDF文件', suggestionKey: 'PDF文件', value: 'File:Macchi2013.pdf', controlType: 'text', status: 'matched' },
    { fieldKey: 'lit-summary', fieldLabel: '摘要', suggestionKey: '核心摘要', value: '综述激光驱动离子加速机制与实验判据。', controlType: 'textarea', status: 'matched' },
    { fieldKey: 'lit-related', fieldLabel: '相关页面', suggestionKey: '关联页面', value: [ 'Theory:TNSA', 'Theory:激光等离子体加速总览' ], controlType: 'tokens', status: 'matched' },
    { fieldKey: 'lit-source', fieldLabel: '来源', suggestionKey: '出处', value: [ 'OpenAlex', 'Theory:基础理论总览' ], controlType: 'tokens', status: 'matched' }
  ]);
});

test('matchStructuredFieldsToInventory matches shot record fields conservatively', () => {
  const inventory = [
    { key: 'shot-date', label: '日期', controlType: 'text' },
    { key: 'shot-run', label: 'Run', controlType: 'text' },
    { key: 'shot-goal', label: '实验目标', controlType: 'text' },
    { key: 'shot-tps-image', label: 'TPS结果图', controlType: 'text' },
    { key: 'shot-rcf-image', label: 'RCF结果截图', controlType: 'text' },
    { key: 'shot-basis', label: '判断依据', controlType: 'textarea' },
    { key: 'shot-obs', label: '主要观测', controlType: 'textarea' },
    { key: 'shot-weekly', label: '周实验日志', controlType: 'text' },
    { key: 'shot-result-file', label: '处理结果文件', controlType: 'text' },
    { key: 'shot-raw-dir', label: '原始数据主目录', controlType: 'text' }
  ];
  const suggestions = {
    实验日期: '2026-03-14',
    run编号: 'Run01',
    本发目标: '扫描 TPS 能区变化',
    TPS结果截图: 'Shot-2026-03-14-Run01-Shot001-TPS-summary.png',
    RCF结果截图: 'Shot-2026-03-14-Run01-Shot001-RCF-stack.png',
    判断依据: 'TPS 截止能量抬升，RCF 主响应层向深层移动。',
    结果摘要: '质子截止能量较上一发抬升。',
    周日志页面: 'Shot:2026-W11 周实验日志',
    处理结果文件: 'Shot-2026-03-14-Run01-analysis.zip',
    原始数据主目录: '/data/shot/2026-03-14/Run01'
  };

  const matches = matchStructuredFieldsToInventory('Shot记录', suggestions, inventory);

  assert.deepEqual(matches, [
    { fieldKey: 'shot-date', fieldLabel: '日期', suggestionKey: '实验日期', value: '2026-03-14', controlType: 'text', status: 'matched' },
    { fieldKey: 'shot-run', fieldLabel: 'Run', suggestionKey: 'run编号', value: 'Run01', controlType: 'text', status: 'matched' },
    { fieldKey: 'shot-goal', fieldLabel: '实验目标', suggestionKey: '本发目标', value: '扫描 TPS 能区变化', controlType: 'text', status: 'matched' },
    { fieldKey: 'shot-tps-image', fieldLabel: 'TPS结果图', suggestionKey: 'TPS结果截图', value: 'Shot-2026-03-14-Run01-Shot001-TPS-summary.png', controlType: 'text', status: 'matched' },
    { fieldKey: 'shot-rcf-image', fieldLabel: 'RCF结果截图', suggestionKey: 'RCF结果截图', value: 'Shot-2026-03-14-Run01-Shot001-RCF-stack.png', controlType: 'text', status: 'matched' },
    { fieldKey: 'shot-basis', fieldLabel: '判断依据', suggestionKey: '判断依据', value: 'TPS 截止能量抬升，RCF 主响应层向深层移动。', controlType: 'textarea', status: 'matched' },
    { fieldKey: 'shot-obs', fieldLabel: '主要观测', suggestionKey: '结果摘要', value: '质子截止能量较上一发抬升。', controlType: 'textarea', status: 'matched' },
    { fieldKey: 'shot-weekly', fieldLabel: '周实验日志', suggestionKey: '周日志页面', value: 'Shot:2026-W11 周实验日志', controlType: 'text', status: 'matched' },
    { fieldKey: 'shot-result-file', fieldLabel: '处理结果文件', suggestionKey: '处理结果文件', value: 'Shot-2026-03-14-Run01-analysis.zip', controlType: 'text', status: 'matched' },
    { fieldKey: 'shot-raw-dir', fieldLabel: '原始数据主目录', suggestionKey: '原始数据主目录', value: '/data/shot/2026-03-14/Run01', controlType: 'text', status: 'matched' }
  ]);
});

test('matchStructuredFieldsToInventory preserves structured suggestion status and evidence for shot fields', () => {
  const inventory = [
    { key: 'shot-run', label: 'Run', controlType: 'text' },
    { key: 'shot-basis', label: '判断依据', controlType: 'textarea' },
    { key: 'shot-raw-dir', label: '原始数据主目录', controlType: 'text' }
  ];
  const suggestions = {
    Run: {
      value: 'Run96',
      status: 'confirmed',
      evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
    },
    判断依据: {
      value: 'TPS 截止能量抬升，建议结合 RCF 复核。',
      status: 'pending',
      reason: '当前只根据结果图给出候选，需要学生确认。',
      evidence: [ '附件 labassistant-shot-check.png' ]
    },
    原始数据主目录: {
      value: '/data/shot/2026-03-23/Run96',
      status: 'needs_review',
      evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
    }
  };

  const matches = matchStructuredFieldsToInventory('Shot记录', suggestions, inventory);

  assert.deepEqual(matches, [
    {
      fieldKey: 'shot-run',
      fieldLabel: 'Run',
      suggestionKey: 'Run',
      value: 'Run96',
      controlType: 'text',
      status: 'confirmed',
      evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
    },
    {
      fieldKey: 'shot-basis',
      fieldLabel: '判断依据',
      suggestionKey: '判断依据',
      value: 'TPS 截止能量抬升，建议结合 RCF 复核。',
      controlType: 'textarea',
      status: 'pending',
      evidence: [ '附件 labassistant-shot-check.png' ],
      reason: '当前只根据结果图给出候选，需要学生确认。'
    },
    {
      fieldKey: 'shot-raw-dir',
      fieldLabel: '原始数据主目录',
      suggestionKey: '原始数据主目录',
      value: '/data/shot/2026-03-23/Run96',
      controlType: 'text',
      status: 'needs_review',
      evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
    }
  ]);
});

test('buildFormFillNotice reports matched field labels and keeps submission explicit', () => {
  const notice = buildFormFillNotice([
    { fieldLabel: '日期' },
    { fieldLabel: 'Run' },
    { fieldLabel: 'TPS结果图' },
    { fieldLabel: '主要观测' }
  ]);

  assert.equal(
    notice,
    '已填入 4 个表单字段：日期、Run、TPS结果图、主要观测；表单尚未提交。'
  );
});

test('buildSubmissionChecklistNotice collapses split date fields and preserves preface', () => {
  const notice = buildSubmissionChecklistNotice(
    [ '日期][day', '日期][month', '日期][year', 'RCF结果截图', '判断依据' ],
    { preface: '已填入 3 个表单字段：日期、Run、TPS结果图；表单尚未提交。' }
  );

  assert.equal(
    notice,
    '已填入 3 个表单字段：日期、Run、TPS结果图；表单尚未提交。 提交前请确认：日期、RCF结果截图、判断依据；这些项还没有自动补全。'
  );
});

test('buildSubmissionChecklistSections separates pending and missing shot fields conservatively', () => {
  const sections = buildSubmissionChecklistSections(
    [
      {
        label: '原始数据主目录',
        reason: '已根据 Shot 标题推断出目录候选，但仍需学生确认。',
        evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
      },
      {
        label: '日期][year',
        evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
      }
    ],
    [
      {
        label: '日期][month',
        reason: '当前只有部分日期信息。',
        evidence: [ '附件 labassistant-shot-check.png' ]
      },
      {
        label: '判断依据',
        reason: '当前没有可直接支撑判断依据的结构化信息。'
      }
    ],
    { preface: '已填入 1 个表单字段：Run；表单尚未提交。' }
  );

  assert.deepEqual(sections, {
    preface: '已填入 1 个表单字段：Run；表单尚未提交。',
    pendingItems: [
      {
        label: '原始数据主目录',
        reason: '已根据 Shot 标题推断出目录候选，但仍需学生确认。',
        evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
      },
      {
        label: '日期',
        reason: '已有候选值，请学生确认后再提交。',
        evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
      }
    ],
    missingItems: [
      {
        label: '判断依据',
        reason: '当前没有可直接支撑判断依据的结构化信息。',
        evidence: []
      }
    ],
    pendingText: '提交前请确认：原始数据主目录、日期；这些字段已有候选值，但仍需学生确认。',
    missingText: '提交前请补充：判断依据；当前还没有可直接回填的候选值。',
    summaryText: '已填入 1 个表单字段：Run；表单尚未提交。 提交前请确认：原始数据主目录、日期；这些字段已有候选值，但仍需学生确认。 提交前请补充：判断依据；当前还没有可直接回填的候选值。'
  });
});

test('buildSubmissionChecklistSections adds conservative item-level fallback descriptions', () => {
  const sections = buildSubmissionChecklistSections(
    [ '原始数据主目录' ],
    [ '判断依据' ]
  );

  assert.deepEqual(sections.pendingItems, [
    {
      label: '原始数据主目录',
      reason: '已有候选值，请学生确认后再提交。',
      evidence: []
    }
  ]);
  assert.deepEqual(sections.missingItems, [
    {
      label: '判断依据',
      reason: '当前还没有可直接回填的候选值。',
      evidence: []
    }
  ]);
});

test('buildResultFillFieldSections groups suggested, pending, and missing shot fields conservatively', () => {
  const sections = buildResultFillFieldSections(
    {
      日期: '2026-03-23',
      Run: 'Run96',
      TPS结果图: 'shot-96-tps.png',
      判断依据: '待确认',
      主要观测: '截止能量抬升。'
    },
    [ '日期][year', '日期][month', '日期][day', '判断依据', 'RCF结果截图' ]
  );

  assert.deepEqual(sections, {
    confirmed: [
      { label: 'Run', value: 'Run96' },
      { label: 'TPS结果图', value: 'shot-96-tps.png' },
      { label: '主要观测', value: '截止能量抬升。' }
    ],
    pending: [
      { label: '日期', value: '2026-03-23' }
    ],
    missing: [ '判断依据', 'RCF结果截图' ]
  });
});

test('buildResultFillFieldSections preserves field-level evidence and explicit pending status', () => {
  const sections = buildResultFillFieldSections(
    {
      日期: {
        value: '2026-03-23',
        status: 'confirmed',
        evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
      },
      Run: {
        value: 'Run96',
        status: 'confirmed',
        evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
      },
      主要观测: {
        value: '截止能量抬升。',
        status: 'pending',
        evidence: [ '附件 labassistant-shot-check.png' ]
      }
    },
    [ 'RCF结果截图' ]
  );

  assert.deepEqual(sections, {
    confirmed: [
      {
        label: '日期',
        value: '2026-03-23',
        evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
      },
      {
        label: 'Run',
        value: 'Run96',
        evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
      }
    ],
    pending: [
      {
        label: '主要观测',
        value: '截止能量抬升。',
        evidence: [ '附件 labassistant-shot-check.png' ]
      }
    ],
    missing: [ 'RCF结果截图' ]
  });
});

test('normalizeMissingItemEntries preserves reasons and evidence while collapsing split date labels', () => {
  const entries = normalizeMissingItemEntries([
    {
      label: '日期][year',
      reason: '当前只识别到日期的部分信息。',
      evidence: [ '当前页 Shot:2026-03-23-Run96-Shot001' ]
    },
    {
      label: '日期][month',
      evidence: [ '附件 labassistant-shot-check.png' ]
    },
    '判断依据'
  ]);

  assert.deepEqual(entries, [
    {
      label: '日期',
      reason: '当前只识别到日期的部分信息。',
      evidence: [
        '当前页 Shot:2026-03-23-Run96-Shot001',
        '附件 labassistant-shot-check.png'
      ]
    },
    {
      label: '判断依据',
      reason: '',
      evidence: []
    }
  ]);
});

test('buildFormFillNotice falls back conservatively when there is nothing to fill', () => {
  assert.equal(buildFormFillNotice([]), '没有可填入的字段。');
});

test('buildFormFillNotice collapses split shot date controls into a single 日期 label', () => {
  const notice = buildFormFillNotice([
    { fieldLabel: '日期][day' },
    { fieldLabel: '日期][month' },
    { fieldLabel: '日期][year' },
    { fieldLabel: 'Run' },
    { fieldLabel: 'TPS结果图' }
  ]);

  assert.equal(
    notice,
    '已填入 3 个表单字段：日期、Run、TPS结果图；表单尚未提交。'
  );
});

test('matchStructuredFieldsToInventory splits shot dates across PageForms day month year controls', () => {
  const inventory = [
    { key: 'shot-date-day', label: '日期][day', controlType: 'text' },
    { key: 'shot-date-month', label: '日期][month', controlType: 'select' },
    { key: 'shot-date-year', label: '日期][year', controlType: 'text' },
    { key: 'shot-run', label: 'Run', controlType: 'text' }
  ];
  const suggestions = {
    日期: '2026-03-23',
    Run: 'Run96'
  };

  const matches = matchStructuredFieldsToInventory('Shot记录', suggestions, inventory);

  assert.deepEqual(matches, [
    { fieldKey: 'shot-date-day', fieldLabel: '日期][day', suggestionKey: '日期', value: '23', controlType: 'text', status: 'matched' },
    { fieldKey: 'shot-date-month', fieldLabel: '日期][month', suggestionKey: '日期', value: '03', controlType: 'select', status: 'matched' },
    { fieldKey: 'shot-date-year', fieldLabel: '日期][year', suggestionKey: '日期', value: '2026', controlType: 'text', status: 'matched' },
    { fieldKey: 'shot-run', fieldLabel: 'Run', suggestionKey: 'Run', value: 'Run96', controlType: 'text', status: 'matched' }
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

test('resolvePageFormRuntimeContext refreshes PageForms fields after lazy form mount', () => {
  const pageFormFields = [
    { key: 'Shot记录[Run]', label: 'Run', controlType: 'text' }
  ];
  let collectCount = 0;

  const context = resolvePageFormRuntimeContext({
    editorMode: 'default',
    resolvedFormName: '',
    pageFormFields: [],
    currentTitle: 'Special:编辑表格/Shot记录/Shot:2026-03-23-Run96-Shot996',
    formContext: { formName: 'Shot记录' },
    hasPageFormRoot: true,
    collectPageFormFields: () => {
      collectCount += 1;
      return pageFormFields;
    }
  });

  assert.equal(context.editorMode, 'pageforms_edit');
  assert.equal(context.resolvedFormName, 'Shot记录');
  assert.deepEqual(context.pageFormFields, pageFormFields);
  assert.equal(collectCount, 1);
});
