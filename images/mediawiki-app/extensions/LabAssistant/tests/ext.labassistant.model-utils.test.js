const test = require('node:test');
const assert = require('node:assert/strict');

const {
  inferModelFamily
} = require('../modules/ext.labassistant.model-utils.js');

test('inferModelFamily maps GPT models to gpt by default', () => {
  assert.equal(inferModelFamily('gpt-5.4'), 'gpt');
  assert.equal(inferModelFamily('gpt-5.4-mini'), 'gpt');
});

test('inferModelFamily maps Claude and Gemini prefixes conservatively', () => {
  assert.equal(inferModelFamily('claude-3.7-sonnet'), 'claude');
  assert.equal(inferModelFamily('gemini-2.5-pro'), 'gemini');
});

test('inferModelFamily falls back to the provided default family or gpt', () => {
  assert.equal(inferModelFamily('', 'claude'), 'claude');
  assert.equal(inferModelFamily('unknown-model'), 'gpt');
});
