const test = require('node:test');
const assert = require('node:assert/strict');

const {
  DEFAULT_MOBILE_BREAKPOINT,
  isCompactWorkspaceVariant,
  resolveShellPresentation,
  shouldHydrateStoredSession
} = require('../modules/ext.labassistant.shell-utils.js');

test('resolveShellPresentation keeps desktop plugin mode non-modal', () => {
  assert.deepEqual(
    resolveShellPresentation(1280),
    {
      shellVariant: 'plugin',
      showBackdrop: false,
      lockBodyScroll: false,
      pointerMode: 'passthrough'
    }
  );
});

test('resolveShellPresentation turns narrow viewports into mobile sheets', () => {
  assert.deepEqual(
    resolveShellPresentation(DEFAULT_MOBILE_BREAKPOINT),
    {
      shellVariant: 'mobile-sheet',
      showBackdrop: true,
      lockBodyScroll: true,
      pointerMode: 'modal'
    }
  );
});

test('isCompactWorkspaceVariant treats plugin-style workspaces as compact shells', () => {
  assert.equal(isCompactWorkspaceVariant('plugin'), true);
  assert.equal(isCompactWorkspaceVariant('mobile-sheet'), true);
  assert.equal(isCompactWorkspaceVariant('drawer'), true);
  assert.equal(isCompactWorkspaceVariant('special'), false);
});

test('shouldHydrateStoredSession keeps special page on a fresh chat by default', () => {
  assert.equal(shouldHydrateStoredSession('special'), false);
  assert.equal(shouldHydrateStoredSession('plugin'), true);
  assert.equal(shouldHydrateStoredSession('drawer'), true);
});
