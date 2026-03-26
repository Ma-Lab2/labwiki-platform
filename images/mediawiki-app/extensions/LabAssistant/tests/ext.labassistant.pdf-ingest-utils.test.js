const test = require('node:test');
const assert = require('node:assert/strict');

const {
  normalizeBlockedItems,
  normalizePdfControlPreview
} = require('../modules/ext.labassistant.pdf-ingest-utils.js');

test('normalizeBlockedItems keeps only actionable blocked entries', () => {
  assert.deepEqual(
    normalizeBlockedItems([
      {
        label: '关键参数与软件',
        reason: '包含下载地址',
        content: '下载地址：http://192.168.0.8/setup'
      },
      {
        label: '空项',
        reason: 'ignored',
        content: ''
      }
    ]),
    [
      {
        label: '关键参数与软件',
        reason: '包含下载地址',
        content: '下载地址：http://192.168.0.8/setup'
      }
    ]
  );
});

test('normalizePdfControlPreview keeps target page, overview page and blocked items', () => {
  assert.deepEqual(
    normalizePdfControlPreview({
      preview_id: 'preview-001',
      target_page: 'Control:怀柔真空管道电机控制流程',
      overview_page: 'Control:控制与运行总览',
      content: '== 页面定位 ==',
      overview_update: '== 助手整理专题 ==',
      blocked_items: [
        {
          label: '操作步骤',
          reason: '包含密码',
          content: '账号 admin 和密码 123456'
        }
      ]
    }),
    {
      preview_id: 'preview-001',
      target_page: 'Control:怀柔真空管道电机控制流程',
      overview_page: 'Control:控制与运行总览',
      content: '== 页面定位 ==',
      overview_update: '== 助手整理专题 ==',
      blocked_items: [
        {
          label: '操作步骤',
          reason: '包含密码',
          content: '账号 admin 和密码 123456'
        }
      ],
      metadata: null
    }
  );
});

test('normalizePdfControlPreview returns null when preview id or target page is missing', () => {
  assert.equal(normalizePdfControlPreview({ preview_id: '', target_page: 'Control:示例' }), null);
  assert.equal(normalizePdfControlPreview({ preview_id: 'preview-001', target_page: '' }), null);
});
