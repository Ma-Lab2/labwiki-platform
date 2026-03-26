const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildSessionExportFileName,
  filterSessionHistoryItems,
  normalizeSessionHistoryItems
} = require('../modules/ext.labassistant.session-export-utils.js');

test('normalizeSessionHistoryItems accepts wrapped payloads and keeps usable fields', () => {
  assert.deepEqual(
    normalizeSessionHistoryItems({
      sessions: [
        {
          session_id: 'session-1',
          current_page: 'Shot:2026-03-25-Run07-Shot004',
          latest_question: '整理这发 shot',
          turn_count: 2
        }
      ]
    }),
    [
      {
        session_id: 'session-1',
        current_page: 'Shot:2026-03-25-Run07-Shot004',
        latest_question: '整理这发 shot',
        turn_count: 2
      }
    ]
  );
});

test('filterSessionHistoryItems matches page title, latest question and session id', () => {
  const items = [
    {
      session_id: 'session-shot',
      current_page: 'Shot:2026-03-25-Run07-Shot004',
      latest_question: '整理这发 shot'
    },
    {
      session_id: 'session-theory',
      current_page: 'Theory:TNSA',
      latest_question: '解释 TNSA'
    }
  ];

  assert.deepEqual(
    filterSessionHistoryItems(items, 'run07').map((item) => item.session_id),
    ['session-shot']
  );
  assert.deepEqual(
    filterSessionHistoryItems(items, '解释').map((item) => item.session_id),
    ['session-theory']
  );
  assert.deepEqual(
    filterSessionHistoryItems(items, 'session-shot').map((item) => item.session_id),
    ['session-shot']
  );
});

test('buildSessionExportFileName prefers current page and sanitizes unsafe characters', () => {
  assert.equal(
    buildSessionExportFileName({
      session_id: '12345678-1234-1234-1234-123456789abc',
      current_page: 'Shot:2026-03-25-Run07-Shot004'
    }),
    'Shot-2026-03-25-Run07-Shot004-session-12345678.md'
  );
  assert.equal(
    buildSessionExportFileName({
      session_id: 'abcdef12-1234-1234-1234-123456789abc',
      current_page: ''
    }),
    'labassistant-session-abcdef12.md'
  );
});
