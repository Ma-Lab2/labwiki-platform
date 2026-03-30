( function () {
  var adminUtils = window.LabAuthAdminUtils;

  function el( tag, attrs, children ) {
    var node = document.createElement( tag );
    Object.entries( attrs || {} ).forEach( function ( entry ) {
      if ( entry[ 0 ] === 'className' ) {
        node.className = entry[ 1 ];
      } else if ( entry[ 0 ] === 'text' ) {
        node.textContent = entry[ 1 ];
      } else if ( entry[ 0 ] === 'html' ) {
        node.innerHTML = entry[ 1 ];
      } else {
        node.setAttribute( entry[ 0 ], entry[ 1 ] );
      }
    } );
    ( children || [] ).forEach( function ( child ) {
      node.appendChild( child );
    } );
    return node;
  }

  function mountAdmin() {
    var root = document.getElementById( 'labauth-admin-root' );
    if ( !root || !window.mw ) {
      return;
    }
    if ( !adminUtils ) {
      root.textContent = '账户后台脚本加载失败，请刷新页面后重试。';
      return;
    }

    var api = new mw.Api();
    var mainPageTitle = mw.config.get( 'wgMainPageTitle' ) || '首页';
    var mainPageUrl = mw.util.getUrl( mainPageTitle );
    var logoutUrl = mw.util.getUrl( 'Special:UserLogout' );
    var notices = el( 'div', { className: 'labauth-status', hidden: 'hidden' } );
    var pendingStat = el( 'strong', { text: '0' } );
    var usersStat = el( 'strong', { text: '0' } );
    var activityStat = el( 'strong', { text: '0' } );
    var modalMount = el( 'div', { className: 'labauth-modal-host' } );
    var pendingSearch = el( 'input', {
      type: 'search',
      className: 'labauth-input labauth-search-input',
      placeholder: '搜索待审核申请'
    } );
    var usersSearch = el( 'input', {
      type: 'search',
      className: 'labauth-input labauth-search-input',
      placeholder: '搜索已创建账户'
    } );
    var usersStatusFilter = el( 'select', {
      className: 'labauth-input labauth-filter-select',
      'aria-label': '筛选账户状态'
    }, [
      el( 'option', { value: '', text: '全部账户状态' } ),
      el( 'option', { value: 'active', text: '仅显示 active' } ),
      el( 'option', { value: 'disabled', text: '仅显示 disabled' } )
    ] );
    var usersSortFilter = el( 'select', {
      className: 'labauth-input labauth-filter-select',
      'aria-label': '账户排序方式'
    }, [
      el( 'option', { value: 'approved_desc', text: '最新开通优先' } ),
      el( 'option', { value: 'approved_asc', text: '最早开通优先' } ),
      el( 'option', { value: 'username_asc', text: '用户名 A-Z' } )
    ] );
    var historySearch = el( 'input', {
      type: 'search',
      className: 'labauth-input labauth-search-input',
      placeholder: '搜索近期处理记录'
    } );
    var historyStatusFilter = el( 'select', {
      className: 'labauth-input labauth-filter-select',
      'aria-label': '筛选审核结果'
    }, [
      el( 'option', { value: '', text: '全部处理结果' } ),
      el( 'option', { value: 'approved', text: '仅显示 approved' } ),
      el( 'option', { value: 'rejected', text: '仅显示 rejected' } )
    ] );
    var historySortFilter = el( 'select', {
      className: 'labauth-input labauth-filter-select',
      'aria-label': '处理记录排序方式'
    }, [
      el( 'option', { value: 'reviewed_desc', text: '最新处理优先' } ),
      el( 'option', { value: 'reviewed_asc', text: '最早处理优先' } )
    ] );
    var pendingSummary = el( 'div', { className: 'labauth-summary labauth-summary-wrap' } );
    var pendingSelectionSummary = el( 'div', { className: 'labauth-summary labauth-selection-summary', text: '未选择' } );
    var usersSummary = el( 'div', { className: 'labauth-summary labauth-summary-wrap' } );
    var usersSelectionSummary = el( 'div', { className: 'labauth-summary labauth-selection-summary', text: '未选择' } );
    var historySummary = el( 'div', { className: 'labauth-summary labauth-summary-wrap' } );
    var activitySearch = el( 'input', {
      type: 'search',
      className: 'labauth-input labauth-search-input',
      placeholder: '搜索后台操作日志'
    } );
    var activityTypeFilter = el( 'select', {
      className: 'labauth-input labauth-filter-select',
      'aria-label': '筛选操作类型'
    }, [
      el( 'option', { value: '', text: '全部操作类型' } ),
      el( 'option', { value: 'request_approved', text: '仅显示审批通过' } ),
      el( 'option', { value: 'request_rejected', text: '仅显示驳回申请' } ),
      el( 'option', { value: 'account_disabled', text: '仅显示停用账户' } ),
      el( 'option', { value: 'account_enabled', text: '仅显示恢复账户' } ),
      el( 'option', { value: 'password_reset', text: '仅显示密码重置' } )
    ] );
    var activityActorSearch = el( 'input', {
      type: 'search',
      className: 'labauth-input labauth-search-input',
      placeholder: '筛选操作人'
    } );
    var activityTargetSearch = el( 'input', {
      type: 'search',
      className: 'labauth-input labauth-search-input',
      placeholder: '筛选操作对象'
    } );
    var activityTimeSearch = el( 'input', {
      type: 'search',
      className: 'labauth-input labauth-search-input',
      placeholder: '筛选时间，如 2026-03-23'
    } );
    var activitySummary = el( 'div', { className: 'labauth-summary labauth-summary-wrap' } );
    var historyResetButton = el( 'button', {
      type: 'button',
      className: 'labauth-button-secondary',
      text: '重置筛选'
    } );
    var pendingResetButton = el( 'button', {
      type: 'button',
      className: 'labauth-button-secondary',
      text: '重置筛选'
    } );
    var pendingClearSelectionButton = el( 'button', {
      type: 'button',
      className: 'labauth-button-secondary',
      text: '清空选择'
    } );
    var usersResetButton = el( 'button', {
      type: 'button',
      className: 'labauth-button-secondary',
      text: '重置筛选'
    } );
    var usersClearSelectionButton = el( 'button', {
      type: 'button',
      className: 'labauth-button-secondary',
      text: '清空选择'
    } );
    var activityResetButton = el( 'button', {
      type: 'button',
      className: 'labauth-button-secondary',
      text: '重置筛选'
    } );
    var pendingBody = el( 'div', { className: 'labauth-list' } );
    var usersBody = el( 'div', { className: 'labauth-list' } );
    var historyBody = el( 'div', { className: 'labauth-list' } );
    var activityBody = el( 'div', { className: 'labauth-list' } );
    var pendingItems = [];
    var userItems = [];
    var historyItems = [];
    var activityItems = [];
    var selectedPendingIds = [];
    var selectedUserIds = [];
    var afterLoadAction = null;
    var historyPanel;
    var activityPanel;

    function queueAfterLoadAction( callback ) {
      afterLoadAction = typeof callback === 'function' ? callback : null;
    }

    function updateSelectionSummaries() {
      pendingSelectionSummary.textContent = adminUtils.summarizeSelectionCount( selectedPendingIds.length );
      usersSelectionSummary.textContent = adminUtils.summarizeSelectionCount( selectedUserIds.length );
      pendingClearSelectionButton.disabled = selectedPendingIds.length === 0;
      usersClearSelectionButton.disabled = selectedUserIds.length === 0;
    }

    function setSelectedPendingIds( ids ) {
      selectedPendingIds = ( ids || [] ).map( function ( value ) {
        return String( value );
      } );
      updateSelectionSummaries();
    }

    function setSelectedUserIds( ids ) {
      selectedUserIds = ( ids || [] ).map( function ( value ) {
        return String( value );
      } );
      updateSelectionSummaries();
    }

    function refreshLists() {
      var filteredPending = adminUtils.filterPendingRequests( pendingItems, pendingSearch.value );
      var filteredUsers = adminUtils.filterManagedUsers(
        userItems,
        usersSearch.value,
        usersStatusFilter.value
      );
      var filteredHistory = adminUtils.filterReviewedRequests(
        historyItems,
        historySearch.value,
        historyStatusFilter.value
      );
      filteredUsers = adminUtils.sortManagedUsers( filteredUsers, usersSortFilter.value );
      filteredHistory = adminUtils.sortReviewedRequests( filteredHistory, historySortFilter.value );
      var filteredActivity = adminUtils.filterAdminEvents(
        activityItems,
        activitySearch.value,
        activityTypeFilter.value,
        activityActorSearch.value,
        activityTargetSearch.value,
        activityTimeSearch.value
      );
      setSelectedPendingIds( adminUtils.syncSelectedIds( selectedPendingIds, filteredPending, 'request_id' ) );
      setSelectedUserIds( adminUtils.syncSelectedIds( selectedUserIds, filteredUsers, 'user_id' ) );
      pendingSummary.textContent = adminUtils.summarizePendingList( {
        filteredCount: filteredPending.length,
        totalCount: pendingItems.length,
        query: pendingSearch.value
      } );
      usersSummary.textContent = adminUtils.summarizeUsersList( {
        filteredCount: filteredUsers.length,
        totalCount: userItems.length,
        query: usersSearch.value,
        statusFilter: usersStatusFilter.value
      } );
      historySummary.textContent = adminUtils.summarizeHistoryList( {
        filteredCount: filteredHistory.length,
        totalCount: historyItems.length,
        query: historySearch.value,
        statusFilter: historyStatusFilter.value
      } );
      activitySummary.textContent = adminUtils.summarizeActivityList( {
        filteredCount: filteredActivity.length,
        totalCount: activityItems.length,
        query: activitySearch.value,
        typeFilter: activityTypeFilter.value,
        actorQuery: activityActorSearch.value,
        targetQuery: activityTargetSearch.value,
        timeQuery: activityTimeSearch.value
      } );
      renderPending( filteredPending );
      renderUsers( filteredUsers );
      renderHistory( filteredHistory );
      renderActivity( filteredActivity );
    }

    function renderActivityTypeOptions() {
      var selectedValue = activityTypeFilter.value;
      var options = adminUtils.buildActivityTypeOptions( activityItems );

      activityTypeFilter.innerHTML = '';
      options.forEach( function ( option ) {
        activityTypeFilter.appendChild( el( 'option', {
          value: option.value,
          text: option.text
        } ) );
      } );

      activityTypeFilter.value = selectedValue;
      if ( activityTypeFilter.value !== selectedValue ) {
        activityTypeFilter.value = '';
      }
    }

    function jumpToSection( panel ) {
      if ( panel && typeof panel.scrollIntoView === 'function' ) {
        panel.scrollIntoView( {
          behavior: 'smooth',
          block: 'start'
        } );
      }
    }

    function applyActivityLinkState( state ) {
      if ( !state ) {
        return;
      }

      activitySearch.value = state.query || '';
      activityTypeFilter.value = state.typeFilter || '';
      activityActorSearch.value = state.actorQuery || '';
      activityTargetSearch.value = state.targetQuery || '';
      activityTimeSearch.value = state.timeQuery || '';
      refreshLists();
      jumpToSection( activityPanel );
    }

    function applyHistoryLinkState( state ) {
      if ( !state ) {
        return;
      }

      historySearch.value = state.query || '';
      historyStatusFilter.value = state.statusFilter || '';
      refreshLists();
      jumpToSection( historyPanel );
    }

    function resetHistoryFilters() {
      historySearch.value = '';
      historyStatusFilter.value = '';
      historySortFilter.value = 'reviewed_desc';
      refreshLists();
    }

    function resetPendingFilters() {
      pendingSearch.value = '';
      refreshLists();
    }

    function resetUserFilters() {
      usersSearch.value = '';
      usersStatusFilter.value = '';
      usersSortFilter.value = 'approved_desc';
      refreshLists();
    }

    function resetActivityFilters() {
      activitySearch.value = '';
      activityTypeFilter.value = '';
      activityActorSearch.value = '';
      activityTargetSearch.value = '';
      activityTimeSearch.value = '';
      refreshLists();
    }

    function updateHeroStats() {
      pendingStat.textContent = String( pendingItems.length );
      usersStat.textContent = String( userItems.length );
      activityStat.textContent = String( activityItems.length );
    }

    function setNotice( type, message ) {
      notices.hidden = false;
      notices.className = 'labauth-status is-' + type;
      notices.textContent = message;
    }

    function clearNotice() {
      notices.hidden = true;
      notices.textContent = '';
    }

    function callAdminAction( params ) {
      clearNotice();
      return api.postWithToken( 'csrf', Object.assign( { format: 'json' }, params ) );
    }

    function closeDialog() {
      modalMount.innerHTML = '';
    }

    function openDialog( options ) {
      return new Promise( function ( resolve ) {
        var fields = options.fields || [];
        var inputs = {};
        var title = el( 'h3', { text: options.title || '确认操作' } );
        var body = el( 'p', { text: options.message || '' } );
        var dialog = el( 'div', { className: 'labauth-modal' }, [ title, body ] );

        fields.forEach( function ( field ) {
          var input;
          if ( field.type === 'textarea' ) {
            input = el( 'textarea', {
              className: 'labauth-input',
              placeholder: field.placeholder || ''
            } );
          } else {
            input = el( 'input', {
              className: 'labauth-input',
              type: field.type || 'text',
              placeholder: field.placeholder || ''
            } );
          }
          if ( field.value ) {
            input.value = field.value;
          }
          inputs[ field.name ] = input;
          dialog.appendChild( el( 'div', { className: 'labauth-field' }, [
            el( 'label', { text: field.label } ),
            input
          ] ) );
        } );

        var cancelButton = el( 'button', {
          type: 'button',
          className: 'labauth-button-secondary',
          text: options.cancelLabel || '取消'
        } );
        var confirmButton = el( 'button', {
          type: 'button',
          className: options.confirmClassName || 'labauth-button-primary',
          text: options.confirmLabel || '确认'
        } );

        cancelButton.addEventListener( 'click', function () {
          closeDialog();
          resolve( null );
        } );

        confirmButton.addEventListener( 'click', function () {
          var values = {};
          var hasError = false;

          fields.forEach( function ( field ) {
            var value = inputs[ field.name ].value.trim();
            values[ field.name ] = value;
            if ( field.required && !value ) {
              hasError = true;
            }
          } );

          if ( hasError ) {
            setNotice( 'error', options.requiredMessage || '请先补全必要信息。' );
            return;
          }

          closeDialog();
          resolve( values );
        } );

        dialog.appendChild( el( 'div', { className: 'labauth-modal-actions' }, [
          cancelButton,
          confirmButton
        ] ) );

        var backdrop = el( 'div', { className: 'labauth-modal-backdrop' }, [ dialog ] );
        backdrop.addEventListener( 'click', function ( event ) {
          if ( event.target === backdrop ) {
            closeDialog();
            resolve( null );
          }
        } );

        modalMount.innerHTML = '';
        modalMount.appendChild( backdrop );
        if ( fields.length && inputs[ fields[ 0 ].name ] ) {
          inputs[ fields[ 0 ].name ].focus();
        }
      } );
    }

    function confirmAction( title, message, confirmLabel ) {
      return openDialog( {
        title: title,
        message: message,
        confirmLabel: confirmLabel || '确认'
      } );
    }

    function createSelectionToggle( checked, labelText, onChange ) {
      var checkbox = el( 'input', {
        type: 'checkbox',
        className: 'labauth-selection-checkbox',
        'aria-label': labelText
      } );
      checkbox.checked = checked;
      checkbox.addEventListener( 'change', function () {
        onChange( checkbox.checked );
      } );

      return el( 'label', { className: 'labauth-selection-toggle' }, [
        checkbox,
        el( 'span', { text: '选择' } )
      ] );
    }

    function renderPending( items ) {
      pendingBody.innerHTML = '';
      if ( !items.length ) {
        pendingBody.appendChild( el( 'div', {
          className: 'labauth-empty',
          text: adminUtils.getPendingEmptyMessage( pendingItems.length, {
            query: pendingSearch.value
          } )
        } ) );
        return;
      }

      items.forEach( function ( item ) {
        var requestId = String( item.request_id );
        var isSelected = selectedPendingIds.includes( requestId );
        var actions = el( 'div', { className: 'labauth-actions' } );
        var approve = el( 'button', {
          type: 'button',
          className: 'labauth-button-primary',
          text: '审批通过'
        } );
        var reject = el( 'button', {
          type: 'button',
          className: 'labauth-button-secondary',
          text: '驳回'
        } );
        var toggleSelect = createSelectionToggle(
          isSelected,
          '选择待审核申请 ' + item.username,
          function ( checked ) {
            setSelectedPendingIds(
              checked ?
                adminUtils.toggleSelectedId( selectedPendingIds, requestId ) :
                selectedPendingIds.filter( function ( value ) {
                  return value !== requestId;
                } )
            );
            renderPending( items );
          }
        );

        approve.addEventListener( 'click', function () {
          setSelectedPendingIds( [ requestId ] );
          confirmAction(
            '通过学生申请',
            '确认通过申请“' + item.username + '”吗？系统会立刻创建账户并写入开通记录。',
            '确认通过'
          ).then( function ( result ) {
            if ( !result ) {
              return;
            }
            queueAfterLoadAction( function () {
              applyHistoryLinkState( {
                query: requestId,
                statusFilter: 'approved'
              } );
            } );
            callAdminAction( {
              action: 'labauthadminapprove',
              request_id: item.request_id
            } ).then( function () {
              setNotice( 'success', '已通过申请：' + item.username + '，账户已创建。' );
              loadAll();
            } ).catch( function ( error ) {
              setNotice( 'error', error && error.message ? error.message : '审批失败。' );
            } );
          } );
        } );

        reject.addEventListener( 'click', function () {
          setSelectedPendingIds( [ requestId ] );
          openDialog( {
            title: '驳回学生申请',
            message: '请填写驳回原因。该原因会进入处理记录和后台操作日志。',
            confirmLabel: '确认驳回',
            fields: [ {
              name: 'review_note',
              label: '驳回原因',
              type: 'textarea',
              required: true,
              placeholder: '请输入驳回原因（必填）'
            } ],
            requiredMessage: '驳回申请时必须填写原因。'
          } ).then( function ( values ) {
            if ( !values ) {
              return;
            }
            queueAfterLoadAction( function () {
              applyHistoryLinkState( {
                query: requestId,
                statusFilter: 'rejected'
              } );
            } );
            callAdminAction( {
              action: 'labauthadminreject',
              request_id: item.request_id,
              review_note: values.review_note
            } ).then( function () {
              setNotice( 'success', '已驳回申请：' + item.username + '。原因：' + values.review_note );
              loadAll();
            } ).catch( function ( error ) {
              setNotice( 'error', error && error.message ? error.message : '驳回失败。' );
            } );
          } );
        } );

        actions.appendChild( approve );
       actions.appendChild( reject );

        pendingBody.appendChild( el( 'article', {
          className: 'labauth-request-card' + ( isSelected ? ' is-selected' : '' )
        }, [
          el( 'div', { className: 'labauth-request-header' }, [
            el( 'div', { className: 'labauth-request-title' }, [
              el( 'strong', { text: item.real_name + ' / ' + item.username } ),
              el( 'span', { className: 'labauth-pill', text: item.status } )
            ] ),
            toggleSelect
          ] ),
          el( 'div', { className: 'labauth-meta', text: '学号：' + item.student_id + '  邮箱：' + item.email } ),
          el( 'div', {
            className: 'labauth-meta',
            text: '提交时间：' + adminUtils.formatAdminTimestamp( item.submitted_at )
          } ),
          actions
        ] ) );
      } );
    }

    function renderUsers( items ) {
      usersBody.innerHTML = '';
      if ( !items.length ) {
        usersBody.appendChild( el( 'div', {
          className: 'labauth-empty',
          text: adminUtils.getUsersEmptyMessage( userItems.length, {
            query: usersSearch.value,
            statusFilter: usersStatusFilter.value
          } )
        } ) );
        return;
      }

      items.forEach( function ( item ) {
        var userId = String( item.user_id );
        var isSelected = selectedUserIds.includes( userId );
        var actions = el( 'div', { className: 'labauth-actions' } );
        var toggle = el( 'button', {
          type: 'button',
          className: 'labauth-button-secondary',
          text: item.account_status === 'disabled' ? '恢复' : '停用'
        } );
        var reset = el( 'button', {
          type: 'button',
          className: 'labauth-button-secondary',
          text: '重置密码'
        } );
        var toggleSelect = createSelectionToggle(
          isSelected,
          '选择已创建账户 ' + item.username,
          function ( checked ) {
            setSelectedUserIds(
              checked ?
                adminUtils.toggleSelectedId( selectedUserIds, userId ) :
                selectedUserIds.filter( function ( value ) {
                  return value !== userId;
                } )
            );
            renderUsers( items );
          }
        );

        toggle.addEventListener( 'click', function () {
          var actionLabel = item.account_status === 'disabled' ? '恢复' : '停用';
          var eventType = item.account_status === 'disabled' ? 'account_enabled' : 'account_disabled';
          setSelectedUserIds( [ userId ] );
          confirmAction(
            actionLabel + '账户',
            '确认' + actionLabel + '账户“' + item.username + '”吗？该操作会写入后台日志。',
            '确认' + actionLabel
          ).then( function ( result ) {
            if ( !result ) {
              return;
            }
            queueAfterLoadAction( function () {
              applyActivityLinkState( {
                query: '',
                typeFilter: eventType,
                actorQuery: '',
                targetQuery: item.username,
                timeQuery: ''
              } );
            } );
            callAdminAction( {
              action: item.account_status === 'disabled' ? 'labauthadminenable' : 'labauthadmindisable',
              user_id: item.user_id
            } ).then( function () {
              setNotice( 'success', '已' + actionLabel + '账户：' + item.username );
              loadAll();
            } ).catch( function ( error ) {
              setNotice( 'error', error && error.message ? error.message : '账户状态更新失败。' );
            } );
          } );
        } );

        reset.addEventListener( 'click', function () {
          setSelectedUserIds( [ userId ] );
          openDialog( {
            title: '重置账户密码',
            message: '请输入“' + item.username + '”的新密码。系统不会自动通知学生，请通过安全渠道发送。',
            confirmLabel: '确认重置',
            fields: [ {
              name: 'new_password',
              label: '新密码',
              type: 'password',
              required: true,
              placeholder: '请输入新密码'
            } ],
            requiredMessage: '请输入新的登录密码。'
          } ).then( function ( values ) {
            if ( !values ) {
              return;
            }
            queueAfterLoadAction( function () {
              applyActivityLinkState( {
                query: '',
                typeFilter: 'password_reset',
                actorQuery: '',
                targetQuery: item.username,
                timeQuery: ''
              } );
            } );
            callAdminAction( {
              action: 'labauthadminresetpassword',
              user_id: item.user_id,
              new_password: values.new_password
            } ).then( function () {
              setNotice( 'success', '已重置密码：' + item.username + '。请通过安全渠道告知新密码。' );
              loadAll();
            } ).catch( function ( error ) {
              setNotice( 'error', error && error.message ? error.message : '密码重置失败。' );
            } );
          } );
        } );

        actions.appendChild( toggle );
        actions.appendChild( reset );

        usersBody.appendChild( el( 'article', {
          className: 'labauth-user-row' + ( isSelected ? ' is-selected' : '' )
        }, [
          el( 'div', { className: 'labauth-request-header' }, [
            el( 'div', { className: 'labauth-request-title' }, [
              el( 'strong', { text: item.real_name + ' / ' + item.username } ),
              el( 'span', { className: 'labauth-pill', text: item.account_status } )
            ] ),
            toggleSelect
          ] ),
          el( 'div', {
            className: 'labauth-meta',
            text: '学号：' + item.student_id + '  邮箱：' + item.email
          } ),
          el( 'div', {
            className: 'labauth-meta',
            text: '开通时间：' + adminUtils.formatAdminTimestamp( item.approved_at )
          } ),
          actions
        ] ) );
      } );
    }

    function renderHistory( items ) {
      historyBody.innerHTML = '';
      if ( !items.length ) {
        historyBody.appendChild( el( 'div', {
          className: 'labauth-empty',
          text: adminUtils.getHistoryEmptyMessage( historyItems.length, {
            query: historySearch.value,
            statusFilter: historyStatusFilter.value
          } )
        } ) );
        return;
      }

      items.forEach( function ( item ) {
        var actions = el( 'div', { className: 'labauth-actions' } );
        var linkedActivityState = adminUtils.buildActivityLinkState( item );
        var jumpToActivity = el( 'button', {
          type: 'button',
          className: 'labauth-button-secondary',
          text: '查看关联日志'
        } );

        jumpToActivity.addEventListener( 'click', function () {
          applyActivityLinkState( linkedActivityState );
        } );
        actions.appendChild( jumpToActivity );

        var noteText = item.review_note ? '审核备注：' + item.review_note : '审核备注：无';
        historyBody.appendChild( el( 'article', { className: 'labauth-request-card' }, [
          el( 'div', { className: 'labauth-request-header' }, [
            el( 'strong', { text: item.real_name + ' / ' + item.username } ),
            el( 'span', { className: 'labauth-pill', text: item.status } )
          ] ),
          el( 'div', {
            className: 'labauth-meta',
            text: '学号：' + item.student_id + '  邮箱：' + item.email
          } ),
          el( 'div', {
            className: 'labauth-meta',
            text: '提交时间：' + adminUtils.formatAdminTimestamp( item.submitted_at ) +
              '  处理时间：' + adminUtils.formatAdminTimestamp( item.reviewed_at )
          } ),
          el( 'div', {
            className: 'labauth-meta',
            text: '审核人：' + ( item.reviewed_by_name || '系统' )
          } ),
          el( 'div', {
            className: 'labauth-meta labauth-meta-note',
            text: noteText
          } ),
          actions
        ] ) );
      } );
    }

    function renderActivity( items ) {
      activityBody.innerHTML = '';
      if ( !items.length ) {
        activityBody.appendChild( el( 'div', {
          className: 'labauth-empty',
          text: adminUtils.getActivityEmptyMessage( activityItems.length, {
            query: activitySearch.value,
            typeFilter: activityTypeFilter.value,
            actorQuery: activityActorSearch.value,
            targetQuery: activityTargetSearch.value,
            timeQuery: activityTimeSearch.value
          } )
        } ) );
        return;
      }

      items.forEach( function ( item ) {
        var activityLabel = adminUtils.formatAdminEventType( item.event_type );
        var historyLinkState = adminUtils.buildHistoryLinkState( item );
        var children = [
          el( 'div', { className: 'labauth-request-header' }, [
            el( 'strong', { text: item.summary } ),
            el( 'span', { className: 'labauth-pill', text: activityLabel } )
          ] ),
          el( 'div', {
            className: 'labauth-meta',
            text: '操作人：' + ( item.actor_name || '系统' ) +
              '  对象：' + ( item.target_username || '未指定' )
          } ),
          el( 'div', {
            className: 'labauth-meta',
            text: '发生时间：' + adminUtils.formatAdminTimestamp( item.created_at )
          } ),
          el( 'div', {
            className: 'labauth-meta labauth-meta-note',
            text: item.details_text ? '详情：' + item.details_text : '详情：无'
          } )
        ];

        if ( item.request_id ) {
          children.splice( 3, 0, el( 'div', {
            className: 'labauth-meta',
            text: '关联申请：#' + item.request_id
          } ) );
        }

        if ( historyLinkState ) {
          var actions = el( 'div', { className: 'labauth-actions' } );
          var jumpToHistory = el( 'button', {
            type: 'button',
            className: 'labauth-button-secondary',
            text: '定位审核记录'
          } );
          jumpToHistory.addEventListener( 'click', function () {
            applyHistoryLinkState( historyLinkState );
          } );
          actions.appendChild( jumpToHistory );
          children.push( actions );
        }

        activityBody.appendChild( el( 'article', { className: 'labauth-request-card' }, children ) );
      } );
    }

    function loadAll() {
      Promise.all( [
        api.get( {
          action: 'labauthadminqueue',
          format: 'json'
        } ),
        api.get( {
          action: 'labauthadminusers',
          format: 'json'
        } ),
        api.get( {
          action: 'labauthadminhistory',
          format: 'json'
        } ),
        api.get( {
          action: 'labauthadminactivity',
          format: 'json'
        } )
      ] ).then( function ( responses ) {
        pendingItems = ( responses[ 0 ].labauthadminqueue || {} ).requests || [];
        userItems = ( responses[ 1 ].labauthadminusers || {} ).users || [];
        historyItems = ( responses[ 2 ].labauthadminhistory || {} ).requests || [];
        activityItems = ( responses[ 3 ].labauthadminactivity || {} ).events || [];
        updateHeroStats();
        renderActivityTypeOptions();
        refreshLists();
        if ( afterLoadAction ) {
          var callback = afterLoadAction;
          afterLoadAction = null;
          callback();
        }
      } ).catch( function ( error ) {
        setNotice( 'error', error && error.message ? error.message : '账户后台加载失败。' );
      } );
    }

    pendingSearch.addEventListener( 'input', refreshLists );
    pendingResetButton.addEventListener( 'click', resetPendingFilters );
    pendingClearSelectionButton.addEventListener( 'click', function () {
      setSelectedPendingIds( [] );
      renderPending( adminUtils.filterPendingRequests( pendingItems, pendingSearch.value ) );
    } );
    usersSearch.addEventListener( 'input', refreshLists );
    usersStatusFilter.addEventListener( 'change', refreshLists );
    usersSortFilter.addEventListener( 'change', refreshLists );
    usersResetButton.addEventListener( 'click', resetUserFilters );
    usersClearSelectionButton.addEventListener( 'click', function () {
      setSelectedUserIds( [] );
      renderUsers( adminUtils.sortManagedUsers(
        adminUtils.filterManagedUsers( userItems, usersSearch.value, usersStatusFilter.value ),
        usersSortFilter.value
      ) );
    } );
    historySearch.addEventListener( 'input', refreshLists );
    historyStatusFilter.addEventListener( 'change', refreshLists );
    historySortFilter.addEventListener( 'change', refreshLists );
    historyResetButton.addEventListener( 'click', resetHistoryFilters );
    activitySearch.addEventListener( 'input', refreshLists );
    activityTypeFilter.addEventListener( 'change', refreshLists );
    activityActorSearch.addEventListener( 'input', refreshLists );
    activityTargetSearch.addEventListener( 'input', refreshLists );
    activityTimeSearch.addEventListener( 'input', refreshLists );
    activityResetButton.addEventListener( 'click', resetActivityFilters );

    historyPanel = el( 'section', { className: 'labauth-panel labauth-panel-wide' }, [
      el( 'div', { className: 'labauth-panel-header' }, [
        el( 'div', { className: 'labauth-panel-header-copy' }, [
          el( 'div', { className: 'labauth-panel-eyebrow', text: 'Review History' } ),
          el( 'h2', { text: '近期处理记录' } ),
          el( 'p', { text: '查看审批结果、审核备注和关联申请，必要时可跳到后台日志继续追踪。' } )
        ] )
      ] ),
      el( 'div', { className: 'labauth-toolbar' }, [
        el( 'div', { className: 'labauth-filter-group' }, [
          historySearch,
          historyStatusFilter,
          historySortFilter
        ] ),
        el( 'div', { className: 'labauth-toolbar-meta' }, [
          historySummary,
          historyResetButton
        ] )
      ] ),
      historyBody
    ] );

    activityPanel = el( 'section', { className: 'labauth-panel labauth-panel-wide' }, [
      el( 'div', { className: 'labauth-panel-header' }, [
        el( 'div', { className: 'labauth-panel-header-copy' }, [
          el( 'div', { className: 'labauth-panel-eyebrow', text: 'Audit Trail' } ),
          el( 'h2', { text: '后台操作日志' } ),
          el( 'p', { text: '集中查看审批、停用、恢复和密码重置等后台事件，并与处理记录互相定位。' } )
        ] )
      ] ),
      el( 'div', { className: 'labauth-toolbar' }, [
        el( 'div', { className: 'labauth-filter-group' }, [
          activitySearch,
          activityTypeFilter,
          activityActorSearch,
          activityTargetSearch,
          activityTimeSearch
        ] ),
        el( 'div', { className: 'labauth-toolbar-meta' }, [
          activitySummary,
          activityResetButton
        ] )
      ] ),
      activityBody
    ] );

    root.appendChild( el( 'div', { className: 'labauth-admin-shell' }, [
      el( 'section', { className: 'labauth-admin-hero' }, [
        el( 'div', { className: 'labauth-admin-hero-top' }, [
          el( 'div', {}, [
            el( 'div', { className: 'labauth-admin-hero-badge', text: 'Admin Console' } ),
            el( 'h1', { text: '账户管理后台' } ),
            el( 'p', {
              className: 'labauth-admin-subtitle',
              text: '以待审核申请为主入口，统一处理学生注册、账号状态与审计记录。'
            } ),
            notices
          ] ),
          el( 'div', { className: 'labauth-admin-hero-actions' }, [
            el( 'a', { className: 'labauth-button-ghost', href: mainPageUrl, text: '返回首页' } ),
            el( 'a', { className: 'labauth-button-ghost', href: logoutUrl, text: '退出登录' } )
          ] )
        ] ),
        el( 'div', { className: 'labauth-admin-stats' }, [
          el( 'div', { className: 'labauth-admin-stat' }, [
            pendingStat,
            el( 'span', { text: '待审核申请' } )
          ] ),
          el( 'div', { className: 'labauth-admin-stat' }, [
            usersStat,
            el( 'span', { text: '已创建账户' } )
          ] ),
          el( 'div', { className: 'labauth-admin-stat' }, [
            activityStat,
            el( 'span', { text: '后台日志条目' } )
          ] )
        ] )
      ] ),
      el( 'div', { className: 'labauth-admin-grid' }, [
        el( 'section', { className: 'labauth-panel labauth-panel-primary' }, [
          el( 'div', { className: 'labauth-panel-header' }, [
            el( 'div', { className: 'labauth-panel-header-copy' }, [
              el( 'div', { className: 'labauth-panel-eyebrow', text: 'Approval Queue' } ),
              el( 'h2', { text: '待审核申请' } ),
              el( 'p', { text: '这一栏优先处理新提交的学生申请。审批通过会直接创建账户，驳回原因会进入处理记录。' } )
            ] )
          ] ),
          el( 'div', { className: 'labauth-toolbar' }, [
            el( 'div', { className: 'labauth-filter-group' }, [
              pendingSearch
            ] ),
            el( 'div', { className: 'labauth-toolbar-meta' }, [
              pendingSummary,
              pendingSelectionSummary,
              pendingClearSelectionButton,
              pendingResetButton
            ] )
          ] ),
          pendingBody
        ] ),
        el( 'section', { className: 'labauth-panel' }, [
          el( 'div', { className: 'labauth-panel-header' }, [
            el( 'div', { className: 'labauth-panel-header-copy' }, [
              el( 'div', { className: 'labauth-panel-eyebrow', text: 'Account State' } ),
              el( 'h2', { text: '已创建账户' } ),
              el( 'p', { text: '集中处理停用、恢复和密码重置。单项操作完成后会自动定位到对应日志。' } )
            ] )
          ] ),
          el( 'div', { className: 'labauth-toolbar' }, [
            el( 'div', { className: 'labauth-filter-group' }, [
              usersSearch,
              usersStatusFilter,
              usersSortFilter
            ] ),
            el( 'div', { className: 'labauth-toolbar-meta' }, [
              usersSummary,
              usersSelectionSummary,
              usersClearSelectionButton,
              usersResetButton
            ] )
          ] ),
          usersBody
        ] ),
        historyPanel,
        activityPanel
      ] ),
      modalMount
    ] ) );

    updateSelectionSummaries();
    loadAll();
  }

  if ( document.readyState === 'loading' ) {
    document.addEventListener( 'DOMContentLoaded', mountAdmin );
  } else {
    mountAdmin();
  }
}() );
