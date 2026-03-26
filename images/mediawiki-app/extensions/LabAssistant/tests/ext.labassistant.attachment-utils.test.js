const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildAttachmentContentUrl,
  extractClipboardFiles,
  resolveApiBase
} = require('../modules/ext.labassistant.attachment-utils.js');

test('resolveApiBase rewrites relative assistant API paths for 127.0.0.1 loopback pages', () => {
  assert.equal(
    resolveApiBase('/tools/assistant/api', {
      protocol: 'http:',
      hostname: '127.0.0.1',
      port: '8443'
    }),
    'http://localhost:8443/tools/assistant/api'
  );
});

test('resolveApiBase leaves non-loopback API paths unchanged', () => {
  assert.equal(
    resolveApiBase('/tools/assistant/api', {
      protocol: 'http:',
      hostname: '192.168.1.2',
      port: '8443'
    }),
    '/tools/assistant/api'
  );
  assert.equal(
    resolveApiBase('http://api.example.test/tools/assistant/api', {
      protocol: 'http:',
      hostname: '127.0.0.1',
      port: '8443'
    }),
    'http://api.example.test/tools/assistant/api'
  );
});

test('extractClipboardFiles keeps file clipboard items and ignores text payloads', () => {
  const screenshot = { name: 'shot.png', type: 'image/png', size: 128 };
  const items = [
    {
      kind: 'string',
      type: 'text/plain',
      getAsFile: () => null
    },
    {
      kind: 'file',
      type: 'image/png',
      getAsFile: () => screenshot
    }
  ];

  assert.deepEqual(extractClipboardFiles(items), [screenshot]);
});

test('buildAttachmentContentUrl reuses resolved API base and attachment id', () => {
  assert.equal(
    buildAttachmentContentUrl('/tools/assistant/api', 'att-pdf-001', {
      protocol: 'http:',
      hostname: '127.0.0.1',
      port: '8443'
    }),
    'http://localhost:8443/tools/assistant/api/attachments/att-pdf-001/content'
  );
});
