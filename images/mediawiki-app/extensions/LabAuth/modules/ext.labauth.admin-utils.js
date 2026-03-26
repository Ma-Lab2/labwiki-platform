( function ( root, factory ) {
  var api = factory();

  if ( typeof module === 'object' && module.exports ) {
    module.exports = api;
  }

  root.LabAuthAdminUtils = api;
}( typeof globalThis !== 'undefined' ? globalThis : this, function () {
  function normalizeAdminSearch( query ) {
    return String( query || '' ).trim().toLowerCase();
  }

  function itemMatchesQuery( item, normalizedQuery, fields ) {
    if ( !normalizedQuery ) {
      return true;
    }

    return fields.some( function ( field ) {
      var value = item && item[ field ] !== undefined && item[ field ] !== null ? String( item[ field ] ) : '';
      return value.toLowerCase().includes( normalizedQuery );
    } );
  }

  function itemMatchesExactFilter( item, field, selectedValue ) {
    if ( !selectedValue ) {
      return true;
    }

    return String( item && item[ field ] !== undefined && item[ field ] !== null ? item[ field ] : '' )
      .toLowerCase() === String( selectedValue ).toLowerCase();
  }

  function eventTypeToLabel( eventType ) {
    var mapping = {
      request_approved: '审批通过',
      request_rejected: '驳回申请',
      account_disabled: '停用账户',
      account_enabled: '恢复账户',
      password_reset: '重置密码'
    };

    return mapping[ eventType ] || String( eventType || '' );
  }

  function getActivityTypeDefinitions() {
    return [
      { value: '', label: '全部操作类型' },
      { value: 'request_approved', label: '仅显示审批通过' },
      { value: 'request_rejected', label: '仅显示驳回申请' },
      { value: 'account_disabled', label: '仅显示停用账户' },
      { value: 'account_enabled', label: '仅显示恢复账户' },
      { value: 'password_reset', label: '仅显示密码重置' }
    ];
  }

  function filterPendingRequests( items, query ) {
    var normalizedQuery = normalizeAdminSearch( query );
    return ( items || [] ).filter( function ( item ) {
      return itemMatchesQuery( item, normalizedQuery, [
        'username',
        'real_name',
        'student_id',
        'email'
      ] );
    } );
  }

  function filterManagedUsers( items, query, statusFilter ) {
    var normalizedQuery = normalizeAdminSearch( query );
    return ( items || [] ).filter( function ( item ) {
      return itemMatchesQuery( item, normalizedQuery, [
        'username',
        'real_name',
        'student_id',
        'email',
        'account_status'
      ] ) && itemMatchesExactFilter( item, 'account_status', statusFilter );
    } );
  }

  function filterReviewedRequests( items, query, statusFilter ) {
    var normalizedQuery = normalizeAdminSearch( query );
    return ( items || [] ).filter( function ( item ) {
      return itemMatchesQuery( item, normalizedQuery, [
        'request_id',
        'username',
        'real_name',
        'student_id',
        'email',
        'status',
        'review_note'
      ] ) && itemMatchesExactFilter( item, 'status', statusFilter );
    } );
  }

  function filterAdminEvents( items, query, typeFilter, actorQuery, targetQuery, timeQuery ) {
    var normalizedQuery = normalizeAdminSearch( query );
    var normalizedActorQuery = normalizeAdminSearch( actorQuery );
    var normalizedTargetQuery = normalizeAdminSearch( targetQuery );
    var normalizedTimeQuery = normalizeAdminSearch( timeQuery );
    return ( items || [] ).filter( function ( item ) {
      return itemMatchesQuery( item, normalizedQuery, [
        'request_id',
        'event_type',
        'actor_name',
        'target_username',
        'summary',
        'details_text'
      ] ) &&
      itemMatchesQuery( item, normalizedActorQuery, [ 'actor_name' ] ) &&
      itemMatchesQuery( item, normalizedTargetQuery, [ 'target_username' ] ) &&
      itemMatchesQuery( {
        created_at: item && item.created_at,
        created_at_formatted: formatAdminTimestamp( item && item.created_at )
      }, normalizedTimeQuery, [ 'created_at', 'created_at_formatted' ] ) &&
      itemMatchesExactFilter( item, 'event_type', typeFilter );
    } );
  }

  function formatAdminEventType( eventType ) {
    return eventTypeToLabel( eventType );
  }

  function buildActivityTypeOptions( items ) {
    var counts = {};
    ( items || [] ).forEach( function ( item ) {
      var key = item && item.event_type ? String( item.event_type ) : '';
      counts[ key ] = ( counts[ key ] || 0 ) + 1;
    } );

    return getActivityTypeDefinitions().map( function ( definition ) {
      var count = definition.value ? ( counts[ definition.value ] || 0 ) : ( items || [] ).length;
      return {
        value: definition.value,
        text: definition.label + '（' + count + '）'
      };
    } );
  }

  function formatAdminTimestamp( raw ) {
    var value = String( raw || '' ).trim();
    if ( !/^\d{14}$/.test( value ) ) {
      return value;
    }

    return value.slice( 0, 4 ) + '-' +
      value.slice( 4, 6 ) + '-' +
      value.slice( 6, 8 ) + ' ' +
      value.slice( 8, 10 ) + ':' +
      value.slice( 10, 12 ) + ':' +
      value.slice( 12, 14 );
  }

  function compareStringsAsc( left, right ) {
    return String( left || '' ).localeCompare( String( right || '' ), 'zh-Hans-CN' );
  }

  function compareTimestamps( left, right ) {
    return String( left || '' ).localeCompare( String( right || '' ) );
  }

  function sortManagedUsers( items, sortMode ) {
    var list = ( items || [] ).slice();
    if ( sortMode === 'approved_asc' ) {
      return list.sort( function ( left, right ) {
        return compareTimestamps( left.approved_at, right.approved_at );
      } );
    }
    if ( sortMode === 'username_asc' ) {
      return list.sort( function ( left, right ) {
        return compareStringsAsc( left.username, right.username );
      } );
    }

    return list.sort( function ( left, right ) {
      return compareTimestamps( right.approved_at, left.approved_at );
    } );
  }

  function sortReviewedRequests( items, sortMode ) {
    var list = ( items || [] ).slice();
    if ( sortMode === 'reviewed_asc' ) {
      return list.sort( function ( left, right ) {
        return compareTimestamps( left.reviewed_at, right.reviewed_at );
      } );
    }

    return list.sort( function ( left, right ) {
      return compareTimestamps( right.reviewed_at, left.reviewed_at );
    } );
  }

  function summarizeAdminLists( counts ) {
    var historyFilteredCount = counts.historyFilteredCount !== undefined ? counts.historyFilteredCount : 0;
    var historyTotalCount = counts.historyTotalCount !== undefined ? counts.historyTotalCount : 0;

    return {
      pending: '显示 ' + counts.pendingFilteredCount + ' / ' + counts.pendingTotalCount + ' 条申请',
      users: '显示 ' + counts.userFilteredCount + ' / ' + counts.userTotalCount + ' 个账户',
      history: '显示 ' + historyFilteredCount + ' / ' + historyTotalCount + ' 条处理记录'
    };
  }

  function hasActivityFilters( filters ) {
    return !!(
      normalizeAdminSearch( filters && filters.query ) ||
      normalizeAdminSearch( filters && filters.typeFilter ) ||
      normalizeAdminSearch( filters && filters.actorQuery ) ||
      normalizeAdminSearch( filters && filters.targetQuery ) ||
      normalizeAdminSearch( filters && filters.timeQuery )
    );
  }

  function summarizeActivityList( details ) {
    var summary = '显示 ' + details.filteredCount + ' / ' + details.totalCount + ' 条后台日志';
    var fragments = [];

    if ( normalizeAdminSearch( details.query ) ) {
      fragments.push( '编号/关键词：' + String( details.query ).trim() );
    }
    if ( normalizeAdminSearch( details.typeFilter ) ) {
      fragments.push( '类型：' + eventTypeToLabel( details.typeFilter ) );
    }
    if ( normalizeAdminSearch( details.actorQuery ) ) {
      fragments.push( '操作人：' + String( details.actorQuery ).trim() );
    }
    if ( normalizeAdminSearch( details.targetQuery ) ) {
      fragments.push( '对象：' + String( details.targetQuery ).trim() );
    }
    if ( normalizeAdminSearch( details.timeQuery ) ) {
      fragments.push( '时间：' + String( details.timeQuery ).trim() );
    }

    return fragments.length ? summary + ' · ' + fragments.join( ' · ' ) : summary;
  }

  function summarizeHistoryList( details ) {
    var summary = '显示 ' + details.filteredCount + ' / ' + details.totalCount + ' 条处理记录';
    var fragments = [];

    if ( normalizeAdminSearch( details.query ) ) {
      fragments.push( '编号/关键词：' + String( details.query ).trim() );
    }
    if ( normalizeAdminSearch( details.statusFilter ) ) {
      fragments.push( '结果：' + String( details.statusFilter ).trim() );
    }

    return fragments.length ? summary + ' · ' + fragments.join( ' · ' ) : summary;
  }

  function summarizePendingList( details ) {
    var summary = '显示 ' + details.filteredCount + ' / ' + details.totalCount + ' 条申请';
    var fragments = [];

    if ( normalizeAdminSearch( details.query ) ) {
      fragments.push( '关键词：' + String( details.query ).trim() );
    }

    return fragments.length ? summary + ' · ' + fragments.join( ' · ' ) : summary;
  }

  function summarizeUsersList( details ) {
    var summary = '显示 ' + details.filteredCount + ' / ' + details.totalCount + ' 个账户';
    var fragments = [];

    if ( normalizeAdminSearch( details.query ) ) {
      fragments.push( '关键词：' + String( details.query ).trim() );
    }
    if ( normalizeAdminSearch( details.statusFilter ) ) {
      fragments.push( '状态：' + String( details.statusFilter ).trim() );
    }

    return fragments.length ? summary + ' · ' + fragments.join( ' · ' ) : summary;
  }

  function getActivityEmptyMessage( totalCount, filters ) {
    if ( totalCount > 0 && hasActivityFilters( filters ) ) {
      return '当前筛选条件下没有匹配的后台操作日志。';
    }

    return '最近还没有后台操作日志。';
  }

  function getHistoryEmptyMessage( totalCount, filters ) {
    if ( totalCount > 0 && (
      normalizeAdminSearch( filters && filters.query ) ||
      normalizeAdminSearch( filters && filters.statusFilter )
    ) ) {
      return '当前筛选条件下没有匹配的处理记录。';
    }

    return '最近还没有处理记录。';
  }

  function getPendingEmptyMessage( totalCount, filters ) {
    if ( totalCount > 0 && normalizeAdminSearch( filters && filters.query ) ) {
      return '当前筛选条件下没有匹配的待审核申请。';
    }

    return '当前没有待审核申请。';
  }

  function getUsersEmptyMessage( totalCount, filters ) {
    if ( totalCount > 0 && (
      normalizeAdminSearch( filters && filters.query ) ||
      normalizeAdminSearch( filters && filters.statusFilter )
    ) ) {
      return '当前筛选条件下没有匹配的已创建账户。';
    }

    return '当前没有已创建的学生账号。';
  }

  function toggleSelectedId( selectedIds, itemId ) {
    var id = String( itemId );
    var list = ( selectedIds || [] ).slice();

    if ( list.some( function ( value ) {
      return String( value ) === id;
    } ) ) {
      return list.filter( function ( value ) {
        return String( value ) !== id;
      } );
    }

    return list.concat( [ itemId ] );
  }

  function syncSelectedIds( selectedIds, items, keyField ) {
    var allowed = new Set( ( items || [] ).map( function ( item ) {
      return String( item && item[ keyField ] );
    } ) );

    return ( selectedIds || [] ).filter( function ( value ) {
      return allowed.has( String( value ) );
    } );
  }

  function summarizeSelectionCount( count ) {
    return count > 0 ? '已选 ' + count + ' 项' : '未选择';
  }

  function buildActivityLinkState( item ) {
    var typeFilter = '';
    if ( item && item.status === 'approved' ) {
      typeFilter = 'request_approved';
    } else if ( item && item.status === 'rejected' ) {
      typeFilter = 'request_rejected';
    }

    return {
      query: item && item.request_id ? String( item.request_id ) : '',
      targetQuery: '',
      timeQuery: '',
      typeFilter: typeFilter
    };
  }

  function buildHistoryLinkState( item ) {
    var statusFilter = '';
    if ( item && item.event_type === 'request_approved' ) {
      statusFilter = 'approved';
    } else if ( item && item.event_type === 'request_rejected' ) {
      statusFilter = 'rejected';
    } else {
      return null;
    }

    return {
      query: item && item.request_id ? String( item.request_id ) : '',
      statusFilter: statusFilter
    };
  }

  return {
    buildActivityTypeOptions: buildActivityTypeOptions,
    buildActivityLinkState: buildActivityLinkState,
    buildHistoryLinkState: buildHistoryLinkState,
    filterReviewedRequests: filterReviewedRequests,
    filterAdminEvents: filterAdminEvents,
    filterManagedUsers: filterManagedUsers,
    filterPendingRequests: filterPendingRequests,
    formatAdminEventType: formatAdminEventType,
    formatAdminTimestamp: formatAdminTimestamp,
    getActivityEmptyMessage: getActivityEmptyMessage,
    getHistoryEmptyMessage: getHistoryEmptyMessage,
    getPendingEmptyMessage: getPendingEmptyMessage,
    getUsersEmptyMessage: getUsersEmptyMessage,
    normalizeAdminSearch: normalizeAdminSearch,
    sortManagedUsers: sortManagedUsers,
    sortReviewedRequests: sortReviewedRequests,
    summarizeActivityList: summarizeActivityList,
    summarizeHistoryList: summarizeHistoryList,
    summarizePendingList: summarizePendingList,
    summarizeSelectionCount: summarizeSelectionCount,
    summarizeUsersList: summarizeUsersList,
    summarizeAdminLists: summarizeAdminLists,
    syncSelectedIds: syncSelectedIds,
    toggleSelectedId: toggleSelectedId
  };
} ) );
