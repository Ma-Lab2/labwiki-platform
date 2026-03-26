const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildClipboardUploadFilename,
  buildWikiImageMarkup,
  insertTextAtCursor,
  isSupportedWikiImageFile
} = require('../modules/ext.labassistant.editor-upload-utils.js');

test('buildClipboardUploadFilename derives a stable wiki-safe name from page title and mime type', () => {
  const name = buildClipboardUploadFilename(
    'Shot:2026-03-22-Run01',
    'image/png',
    new Date('2026-03-22T13:20:30Z')
  );

  assert.equal(name, 'Shot-2026-03-22-Run01-20260322-132030.png');
});

test('buildWikiImageMarkup produces a new line separated file embed', () => {
  assert.equal(
    buildWikiImageMarkup('Shot-1.png'),
    '\n[[File:Shot-1.png|thumb]]\n'
  );
});

test('insertTextAtCursor replaces the current selection and advances the caret', () => {
  const textarea = {
    value: 'before after',
    selectionStart: 7,
    selectionEnd: 12,
    focusCalled: false,
    dispatchEvent: () => {},
    focus() {
      this.focusCalled = true;
    }
  };

  insertTextAtCursor(textarea, 'inserted');

  assert.equal(textarea.value, 'before inserted');
  assert.equal(textarea.selectionStart, 15);
  assert.equal(textarea.selectionEnd, 15);
  assert.equal(textarea.focusCalled, true);
});

test('isSupportedWikiImageFile accepts only paste-friendly image formats', () => {
  assert.equal(isSupportedWikiImageFile({ type: 'image/png' }), true);
  assert.equal(isSupportedWikiImageFile({ type: 'image/jpeg' }), true);
  assert.equal(isSupportedWikiImageFile({ type: 'image/webp' }), true);
  assert.equal(isSupportedWikiImageFile({ type: 'text/plain' }), false);
});
