const test = require('node:test');
const assert = require('node:assert/strict');

const {
  buildActivityTypeOptions,
  buildActivityLinkState,
  buildHistoryLinkState,
  filterAdminEvents,
  filterPendingRequests,
  filterManagedUsers,
  filterReviewedRequests,
  formatAdminEventType,
  formatAdminTimestamp,
  getActivityEmptyMessage,
  getHistoryEmptyMessage,
  getPendingEmptyMessage,
  getUsersEmptyMessage,
  sortManagedUsers,
  sortReviewedRequests,
  summarizeActivityList,
  summarizeAdminLists
  ,
  summarizeHistoryList,
  summarizePendingList,
  summarizeUsersList,
  summarizeSelectionCount,
  syncSelectedIds,
  toggleSelectedId
} = require('../modules/ext.labauth.admin-utils.js');

test('filterPendingRequests matches username, real name, student id, and email', () => {
  const items = [
    {
      username: 'Student 101',
      real_name: '张三',
      student_id: 'S101',
      email: 'student101@example.com'
    },
    {
      username: 'Student 202',
      real_name: '李四',
      student_id: 'S202',
      email: 'student202@example.com'
    }
  ];

  assert.deepEqual(
    filterPendingRequests(items, 'zhang').map((item) => item.username),
    []
  );
  assert.deepEqual(
    filterPendingRequests(items, '张三').map((item) => item.username),
    ['Student 101']
  );
  assert.deepEqual(
    filterPendingRequests(items, 's202').map((item) => item.username),
    ['Student 202']
  );
  assert.deepEqual(
    filterPendingRequests(items, 'student101@').map((item) => item.username),
    ['Student 101']
  );
});

test('filterManagedUsers trims query and matches account status fields case-insensitively', () => {
  const items = [
    {
      username: 'Student 301',
      real_name: '王五',
      student_id: 'S301',
      email: 'student301@example.com',
      account_status: 'active'
    },
    {
      username: 'Student 302',
      real_name: '赵六',
      student_id: 'S302',
      email: 'student302@example.com',
      account_status: 'disabled'
    }
  ];

  assert.deepEqual(
    filterManagedUsers(items, '  DISABLED ').map((item) => item.username),
    ['Student 302']
  );
  assert.deepEqual(
    filterManagedUsers(items, 'student 301').map((item) => item.username),
    ['Student 301']
  );
  assert.deepEqual(
    filterManagedUsers(items, '', 'disabled').map((item) => item.username),
    ['Student 302']
  );
});

test('summarizePendingList includes active search query', () => {
  assert.equal(
    summarizePendingList({
      filteredCount: 1,
      totalCount: 3,
      query: 'student_22'
    }),
    '显示 1 / 3 条申请 · 关键词：student_22'
  );
});

test('summarizeUsersList includes search and status filters', () => {
  assert.equal(
    summarizeUsersList({
      filteredCount: 2,
      totalCount: 8,
      query: 'admin',
      statusFilter: 'disabled'
    }),
    '显示 2 / 8 个账户 · 关键词：admin · 状态：disabled'
  );
});

test('pending and user empty messages distinguish empty data and filtered empty states', () => {
  assert.equal(
    getPendingEmptyMessage(0, { query: '' }),
    '当前没有待审核申请。'
  );
  assert.equal(
    getPendingEmptyMessage(3, { query: 'not-found' }),
    '当前筛选条件下没有匹配的待审核申请。'
  );
  assert.equal(
    getUsersEmptyMessage(0, { query: '', statusFilter: '' }),
    '当前没有已创建的学生账号。'
  );
  assert.equal(
    getUsersEmptyMessage(8, { query: '', statusFilter: 'disabled' }),
    '当前筛选条件下没有匹配的已创建账户。'
  );
});

test('selection helpers toggle ids, prune stale selections, and summarize counts', () => {
  assert.deepEqual(toggleSelectedId([], 3), [3]);
  assert.deepEqual(toggleSelectedId([3, 5], 3), [5]);
  assert.deepEqual(syncSelectedIds([1, 3, 5], [
    { request_id: 1 },
    { request_id: 5 }
  ], 'request_id'), [1, 5]);
  assert.equal(summarizeSelectionCount(0), '未选择');
  assert.equal(summarizeSelectionCount(2), '已选 2 项');
});

test('summarizeAdminLists returns count strings for filtered and total items', () => {
  assert.deepEqual(
    summarizeAdminLists({
      pendingFilteredCount: 1,
      pendingTotalCount: 3,
      userFilteredCount: 2,
      userTotalCount: 2,
      historyFilteredCount: 4,
      historyTotalCount: 5
    }),
    {
      history: '显示 4 / 5 条处理记录',
      pending: '显示 1 / 3 条申请',
      users: '显示 2 / 2 个账户'
    }
  );
});

test('filterReviewedRequests matches review notes and status', () => {
  const items = [
    {
      request_id: 401,
      username: 'Student 401',
      real_name: '孙七',
      student_id: 'S401',
      email: 'student401@example.com',
      status: 'approved',
      review_note: ''
    },
    {
      request_id: 402,
      username: 'Student 402',
      real_name: '周八',
      student_id: 'S402',
      email: 'student402@example.com',
      status: 'rejected',
      review_note: '学号信息不完整'
    }
  ];

  assert.deepEqual(
    filterReviewedRequests(items, 'rejected').map((item) => item.username),
    ['Student 402']
  );
  assert.deepEqual(
    filterReviewedRequests(items, '学号').map((item) => item.username),
    ['Student 402']
  );
  assert.deepEqual(
    filterReviewedRequests(items, '', 'approved').map((item) => item.username),
    ['Student 401']
  );
  assert.deepEqual(
    filterReviewedRequests(items, '402').map((item) => item.username),
    ['Student 402']
  );
});

test('formatAdminTimestamp converts MediaWiki timestamp to readable local format', () => {
  assert.equal(formatAdminTimestamp('20260323011234'), '2026-03-23 01:12:34');
  assert.equal(formatAdminTimestamp(''), '');
  assert.equal(formatAdminTimestamp('bad-value'), 'bad-value');
});

test('sortManagedUsers orders rows by approved time or username', () => {
  const items = [
    { username: 'Student B', approved_at: '20260323010101' },
    { username: 'Student A', approved_at: '20260323020202' },
    { username: 'Student C', approved_at: '20260322030303' }
  ];

  assert.deepEqual(
    sortManagedUsers(items, 'approved_desc').map((item) => item.username),
    ['Student A', 'Student B', 'Student C']
  );
  assert.deepEqual(
    sortManagedUsers(items, 'approved_asc').map((item) => item.username),
    ['Student C', 'Student B', 'Student A']
  );
  assert.deepEqual(
    sortManagedUsers(items, 'username_asc').map((item) => item.username),
    ['Student A', 'Student B', 'Student C']
  );
});

test('sortReviewedRequests orders rows by reviewed time', () => {
  const items = [
    { username: 'Student B', reviewed_at: '20260323010101' },
    { username: 'Student A', reviewed_at: '20260323020202' },
    { username: 'Student C', reviewed_at: '20260322030303' }
  ];

  assert.deepEqual(
    sortReviewedRequests(items, 'reviewed_desc').map((item) => item.username),
    ['Student A', 'Student B', 'Student C']
  );
  assert.deepEqual(
    sortReviewedRequests(items, 'reviewed_asc').map((item) => item.username),
    ['Student C', 'Student B', 'Student A']
  );
});

test('filterAdminEvents matches query, event type, actor, target, and time filters', () => {
  const items = [
    {
      request_id: 11,
      event_type: 'password_reset',
      actor_name: 'Admin',
      target_username: 'Student A',
      summary: '重置密码：Student A',
      details_text: '通过安全渠道通知',
      created_at: '20260323093000'
    },
    {
      request_id: 12,
      event_type: 'account_disabled',
      actor_name: 'Teacher',
      target_username: 'Student B',
      summary: '停用账户：Student B',
      details_text: '实验资格暂停',
      created_at: '20260322101530'
    }
  ];

  assert.deepEqual(
    filterAdminEvents(items, 'admin', '', '', '', '').map((item) => item.target_username),
    ['Student A']
  );
  assert.deepEqual(
    filterAdminEvents(items, '', 'account_disabled', '', '', '').map((item) => item.target_username),
    ['Student B']
  );
  assert.deepEqual(
    filterAdminEvents(items, '', '', 'teacher', '', '').map((item) => item.target_username),
    ['Student B']
  );
  assert.deepEqual(
    filterAdminEvents(items, '', '', '', 'student a', '').map((item) => item.target_username),
    ['Student A']
  );
  assert.deepEqual(
    filterAdminEvents(items, '', '', '', '', '2026-03-22').map((item) => item.target_username),
    ['Student B']
  );
  assert.deepEqual(
    filterAdminEvents(items, '12', '', '', '', '').map((item) => item.target_username),
    ['Student B']
  );
});

test('formatAdminEventType returns readable Chinese labels', () => {
  assert.equal(formatAdminEventType('request_approved'), '审批通过');
  assert.equal(formatAdminEventType('account_enabled'), '恢复账户');
  assert.equal(formatAdminEventType('unknown_type'), 'unknown_type');
});

test('buildActivityLinkState maps reviewed requests to activity filters', () => {
  assert.deepEqual(
    buildActivityLinkState({
      request_id: 901,
      status: 'approved',
      username: 'student_a'
    }),
    {
      query: '901',
      targetQuery: '',
      timeQuery: '',
      typeFilter: 'request_approved'
    }
  );
  assert.deepEqual(
    buildActivityLinkState({
      request_id: 902,
      status: 'rejected',
      username: 'student_b'
    }),
    {
      query: '902',
      targetQuery: '',
      timeQuery: '',
      typeFilter: 'request_rejected'
    }
  );
});

test('buildHistoryLinkState maps request-related events back to review history filters', () => {
  assert.deepEqual(
    buildHistoryLinkState({
      request_id: 901,
      event_type: 'request_approved',
      target_username: 'Student A'
    }),
    {
      query: '901',
      statusFilter: 'approved'
    }
  );
  assert.deepEqual(
    buildHistoryLinkState({
      request_id: 902,
      event_type: 'request_rejected',
      target_username: 'Student B'
    }),
    {
      query: '902',
      statusFilter: 'rejected'
    }
  );
  assert.equal(
    buildHistoryLinkState({
      event_type: 'password_reset',
      target_username: 'Student C'
    }),
    null
  );
});

test('buildActivityTypeOptions returns readable labels with counts', () => {
  const items = [
    { event_type: 'request_approved' },
    { event_type: 'request_approved' },
    { event_type: 'password_reset' }
  ];

  assert.deepEqual(
    buildActivityTypeOptions(items).map((item) => item.text),
    [
      '全部操作类型（3）',
      '仅显示审批通过（2）',
      '仅显示驳回申请（0）',
      '仅显示停用账户（0）',
      '仅显示恢复账户（0）',
      '仅显示密码重置（1）'
    ]
  );
});

test('summarizeActivityList includes active filter labels', () => {
  assert.equal(
    summarizeActivityList({
      filteredCount: 2,
      totalCount: 9,
      query: '22',
      typeFilter: 'request_approved',
      actorQuery: 'admin',
      targetQuery: 'student_a',
      timeQuery: '2026-03-23'
    }),
    '显示 2 / 9 条后台日志 · 编号/关键词：22 · 类型：审批通过 · 操作人：admin · 对象：student_a · 时间：2026-03-23'
  );
});

test('getActivityEmptyMessage distinguishes empty data and filtered empty states', () => {
  assert.equal(
    getActivityEmptyMessage(0, {
      query: '',
      typeFilter: '',
      actorQuery: '',
      targetQuery: '',
      timeQuery: ''
    }),
    '最近还没有后台操作日志。'
  );
  assert.equal(
    getActivityEmptyMessage(8, {
      query: '',
      typeFilter: 'account_disabled',
      actorQuery: '',
      targetQuery: '',
      timeQuery: ''
    }),
    '当前筛选条件下没有匹配的后台操作日志。'
  );
});

test('summarizeHistoryList includes active review filters', () => {
  assert.equal(
    summarizeHistoryList({
      filteredCount: 1,
      totalCount: 6,
      query: '402',
      statusFilter: 'rejected'
    }),
    '显示 1 / 6 条处理记录 · 编号/关键词：402 · 结果：rejected'
  );
});

test('getHistoryEmptyMessage distinguishes empty data and filtered empty states', () => {
  assert.equal(
    getHistoryEmptyMessage(0, {
      query: '',
      statusFilter: ''
    }),
    '最近还没有处理记录。'
  );
  assert.equal(
    getHistoryEmptyMessage(6, {
      query: '',
      statusFilter: 'approved'
    }),
    '当前筛选条件下没有匹配的处理记录。'
  );
});
