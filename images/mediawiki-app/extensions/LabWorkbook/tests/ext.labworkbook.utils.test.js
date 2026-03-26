const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildShotPageTitle,
  collectSheetColumns,
  filterMainLogRows,
  formatSheetTypeLabel
} = require('../modules/ext.labworkbook.utils.js');

test('formatSheetTypeLabel renders stable Chinese labels for workbook sheets', () => {
  assert.equal(formatSheetTypeLabel('main_log'), '主台账');
  assert.equal(formatSheetTypeLabel('plan'), '打靶计划');
  assert.equal(formatSheetTypeLabel('target_grid'), '靶位图');
  assert.equal(formatSheetTypeLabel('calibration'), '标定页');
  assert.equal(formatSheetTypeLabel('matrix'), '表格页');
  assert.equal(formatSheetTypeLabel('unknown_type'), 'unknown_type');
});

test('buildShotPageTitle requires run label, date, and shot number', () => {
  assert.equal(
    buildShotPageTitle({
      runLabel: 'Run96',
      row: {
        时间: '2025-09-26 19:29:54',
        No: '12'
      }
    }),
    'Shot:2025-09-26-Run96-Shot012'
  );

  assert.equal(
    buildShotPageTitle({
      runLabel: '',
      row: {
        时间: '2025-09-26 19:29:54',
        No: '12'
      }
    }),
    ''
  );

  assert.equal(
    buildShotPageTitle({
      runLabel: 'Run96',
      row: {
        时间: '',
        No: '12'
      }
    }),
    ''
  );
});

test('collectSheetColumns preserves explicit columns and falls back to row keys', () => {
  assert.deepEqual(
    collectSheetColumns({
      columns: [ '时间', 'No', '靶类型' ],
      rows: [
        { 时间: '2025-09-26 19:29:54', No: '12', 靶类型: 'Cu100nm 5°' }
      ]
    }),
    [ '时间', 'No', '靶类型' ]
  );

  assert.deepEqual(
    collectSheetColumns({
      rows: [
        { A: '1', B: '2' },
        { A: '3', C: '4' }
      ]
    }),
    [ 'A', 'B', 'C' ]
  );
});

test('filterMainLogRows matches conservative workbook fields and keeps original order', () => {
  const rows = [
    {
      时间: '2025-09-26 17:01:48',
      No: '1',
      靶类型: '空发',
      靶位: '0',
      备注: ''
    },
    {
      时间: '2025-09-26 17:12:24',
      No: '5',
      靶类型: 'ch1000nm 5°',
      靶位: '21-24',
      备注: '首发'
    },
    {
      时间: '2025-09-26 19:29:54',
      No: '96',
      靶类型: 'Cu100nm 5°',
      靶位: '14-3',
      备注: '烧蚀180s'
    }
  ];

  assert.deepEqual(
    filterMainLogRows( rows, 'cu100' ).map( function ( row ) {
      return row.No;
    } ),
    [ '96' ]
  );

  assert.deepEqual(
    filterMainLogRows( rows, '21-24' ).map( function ( row ) {
      return row.No;
    } ),
    [ '5' ]
  );

  assert.deepEqual(
    filterMainLogRows( rows, '烧蚀' ).map( function ( row ) {
      return row.No;
    } ),
    [ '96' ]
  );

  assert.deepEqual(
    filterMainLogRows( rows, '2025-09-26' ).map( function ( row ) {
      return row.No;
    } ),
    [ '1', '5', '96' ]
  );
});
