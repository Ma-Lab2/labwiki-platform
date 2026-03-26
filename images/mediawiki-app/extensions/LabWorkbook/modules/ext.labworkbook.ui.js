( function () {
  var utils = window.LabWorkbookUtils;

  function el( tag, attrs, children ) {
    var node = document.createElement( tag );
    Object.entries( attrs || {} ).forEach( function ( entry ) {
      if ( entry[ 0 ] === 'className' ) {
        node.className = entry[ 1 ];
      } else if ( entry[ 0 ] === 'text' ) {
        node.textContent = entry[ 1 ];
      } else if ( entry[ 0 ] === 'html' ) {
        node.innerHTML = entry[ 1 ];
      } else if ( entry[ 1 ] === false || entry[ 1 ] === null || entry[ 1 ] === undefined ) {
        return;
      } else {
        node.setAttribute( entry[ 0 ], entry[ 1 ] );
      }
    } );
    ( children || [] ).forEach( function ( child ) {
      node.appendChild( child );
    } );
    return node;
  }

  function cloneSheet( sheet ) {
    return JSON.parse( JSON.stringify( sheet || {} ) );
  }

  function escapeHtml( value ) {
    return String( value || '' )
      .replaceAll( '&', '&amp;' )
      .replaceAll( '<', '&lt;' )
      .replaceAll( '>', '&gt;' )
      .replaceAll( '"', '&quot;' )
      .replaceAll( '\'', '&#39;' );
  }

  function mountWorkbook() {
    var root = document.getElementById( 'labworkbook-root' );
    var config = window.mw && mw.config.get( 'wgLabWorkbook' );
    if ( !root || !window.mw || !utils ) {
      return;
    }

    var api = new mw.Api();
    var state = {
      selectedSlug: String( ( config && config.selectedSlug ) || '' ),
      workbook: null,
      workbooks: [],
      activeSheetKey: '',
      draftSheets: {},
      sheetFilters: {}
    };

    var status = el( 'div', { className: 'labworkbook-status', hidden: 'hidden' } );
    var toolbar = el( 'div', { className: 'labworkbook-toolbar' } );
    var summary = el( 'div', { className: 'labworkbook-summary' } );
    var tabs = el( 'div', { className: 'labworkbook-tabs' } );
    var panel = el( 'div', { className: 'labworkbook-panel' } );

    root.appendChild( status );
    root.appendChild( toolbar );
    root.appendChild( summary );
    root.appendChild( tabs );
    root.appendChild( panel );

    function setStatus( kind, message ) {
      status.hidden = !message;
      status.className = 'labworkbook-status' + ( kind ? ' is-' + kind : '' );
      status.textContent = message || '';
    }

    function getDraftSheet( sheetKey ) {
      if ( !state.workbook || !sheetKey ) {
        return null;
      }
      if ( !state.draftSheets[ sheetKey ] ) {
        var source = ( state.workbook.sheets || [] ).find( function ( sheet ) {
          return sheet.sheet_key === sheetKey;
        } );
        if ( source ) {
          state.draftSheets[ sheetKey ] = cloneSheet( source );
        }
      }
      return state.draftSheets[ sheetKey ] || null;
    }

    function renderToolbar() {
      toolbar.innerHTML = '';
      if ( !state.workbooks.length ) {
        toolbar.appendChild( el( 'div', { className: 'labworkbook-empty', text: '当前没有可用的实验工作簿。' } ) );
        return;
      }

      var selector = el( 'select', { className: 'labworkbook-input', 'aria-label': '切换实验工作簿' } );
      state.workbooks.forEach( function ( workbook ) {
        selector.appendChild( el( 'option', {
          value: workbook.slug,
          text: workbook.title + ' · ' + workbook.source_filename,
          selected: workbook.slug === state.selectedSlug ? 'selected' : null
        } ) );
      } );
      selector.addEventListener( 'change', function () {
        state.selectedSlug = selector.value;
        loadWorkbook( state.selectedSlug );
      } );

      toolbar.appendChild( el( 'label', { className: 'labworkbook-field' }, [
        el( 'span', { className: 'labworkbook-label', text: '实验工作簿' } ),
        selector
      ] ) );
    }

    function renderSummary() {
      summary.innerHTML = '';
      if ( !state.workbook ) {
        return;
      }

      var runInput = el( 'input', {
        className: 'labworkbook-input',
        type: 'text',
        value: state.workbook.run_label || '',
        placeholder: '例如 Run96'
      } );
      var saveRunButton = el( 'button', {
        type: 'button',
        className: 'labworkbook-button',
        text: '保存 Run 标签'
      } );

      saveRunButton.addEventListener( 'click', function () {
        setStatus( '', '' );
        api.postWithToken( 'csrf', {
          action: 'labworkbooksave',
          format: 'json',
          slug: state.workbook.slug,
          run_label: runInput.value
        } ).then( function ( data ) {
          state.workbook = data.labworkbooksave.workbook;
          state.workbooks = state.workbooks.map( function ( item ) {
            return item.slug === state.workbook.slug ? state.workbook : item;
          } );
          setStatus( 'success', '已保存工作簿 Run 标签。' );
          render();
        } ).catch( function ( error ) {
          setStatus( 'error', error && error.message ? error.message : '保存 Run 标签失败。' );
        } );
      } );

      summary.appendChild( el( 'div', { className: 'labworkbook-card labworkbook-card-meta' }, [
        el( 'div', { className: 'labworkbook-meta-line', html: '<strong>源文件：</strong>' + escapeHtml( state.workbook.source_filename || '' ) } ),
        el( 'div', { className: 'labworkbook-meta-line', html: '<strong>工作表数：</strong>' + String( ( state.workbook.sheets || [] ).length ) } ),
        el( 'label', { className: 'labworkbook-field' }, [
          el( 'span', { className: 'labworkbook-label', text: 'Run 标签' } ),
          runInput
        ] ),
        saveRunButton,
        el( 'p', {
          className: 'labworkbook-help',
          text: '当前 Excel 原表没有稳定的 Run 列，生成 Shot 页面前需要先在这里明确填写。'
        } )
      ] ) );
    }

    function updateDraftFromTable( table, sheet ) {
      if ( !table || !sheet ) {
        return;
      }
      if ( Array.isArray( sheet.rows ) ) {
        var rowInputs = table.querySelectorAll( 'tbody tr[data-row-index]' );
        rowInputs.forEach( function ( tr ) {
          var rowIndex = Number( tr.getAttribute( 'data-row-index' ) );
          var nextRow = {};
          tr.querySelectorAll( 'input[data-column]' ).forEach( function ( input ) {
            nextRow[ input.getAttribute( 'data-column' ) ] = input.value;
          } );
          sheet.rows[ rowIndex ] = nextRow;
        } );
      }
      if ( Array.isArray( sheet.grid ) ) {
        var gridInputs = table.querySelectorAll( 'tbody tr[data-grid-row]' );
        gridInputs.forEach( function ( tr ) {
          var gridRowIndex = Number( tr.getAttribute( 'data-grid-row' ) );
          sheet.grid[ gridRowIndex ] = sheet.grid[ gridRowIndex ] || [];
          tr.querySelectorAll( 'input[data-grid-col]' ).forEach( function ( input ) {
            var gridColIndex = Number( input.getAttribute( 'data-grid-col' ) );
            sheet.grid[ gridRowIndex ][ gridColIndex ] = input.value;
          } );
        } );
      }
    }

    function persistSheet( sheet ) {
      return api.postWithToken( 'csrf', {
        action: 'labworkbooksave',
        format: 'json',
        slug: state.workbook.slug,
        sheet_key: sheet.sheet_key,
        sheet_data: JSON.stringify( sheet )
      } ).then( function ( data ) {
        state.workbook = data.labworkbooksave.workbook;
        state.draftSheets = {};
        return state.workbook;
      } );
    }

    function createSaveSheetButton( sheet, table ) {
      var button = el( 'button', {
        type: 'button',
        className: 'labworkbook-button',
        text: '保存当前工作表'
      } );

      button.addEventListener( 'click', function () {
        updateDraftFromTable( table, sheet );
        persistSheet( sheet ).then( function () {
          setStatus( 'success', '已保存当前工作表。' );
          render();
        } ).catch( function ( error ) {
          setStatus( 'error', error && error.message ? error.message : '保存工作表失败。' );
        } );
      } );

      return button;
    }

    function createShotOpenLink( pageTitle ) {
      if ( !pageTitle ) {
        return null;
      }

      return el( 'a', {
        className: 'labworkbook-inline-link',
        href: mw.util.getUrl( pageTitle ),
        target: '_blank',
        rel: 'noopener',
        text: '打开 Shot 页面'
      } );
    }

    function renderSheetTable( sheet ) {
      var wrapper = el( 'div', { className: 'labworkbook-card' } );
      var header = el( 'div', { className: 'labworkbook-sheet-header' } );
      var table = el( 'table', { className: 'labworkbook-table' } );
      var sheetFilterValue = state.sheetFilters[ sheet.sheet_key ] || '';
      wrapper.appendChild( header );
      wrapper.appendChild( table );

      header.appendChild( el( 'div', { className: 'labworkbook-sheet-title', text: sheet.sheet_name + ' · ' + utils.formatSheetTypeLabel( sheet.type ) } ) );
      if ( sheet.type === 'main_log' ) {
        var searchInput = el( 'input', {
          className: 'labworkbook-input',
          type: 'search',
          placeholder: '筛选 No / 靶类型 / 靶位 / 备注 / 时间',
          value: sheetFilterValue
        } );
        searchInput.addEventListener( 'input', function () {
          state.sheetFilters[ sheet.sheet_key ] = searchInput.value;
          renderTabs();
        } );
        header.appendChild( searchInput );
      }
      header.appendChild( createSaveSheetButton( sheet, table ) );

      if ( Array.isArray( sheet.rows ) ) {
        var columns = utils.collectSheetColumns( sheet );
        var renderedRows = sheet.type === 'main_log'
          ? utils.filterMainLogRows( sheet.rows || [], sheetFilterValue )
          : ( sheet.rows || [] );
        var thead = el( 'thead' );
        var headRow = el( 'tr' );
        columns.forEach( function ( column ) {
          headRow.appendChild( el( 'th', { text: column } ) );
        } );
        if ( sheet.type === 'main_log' ) {
          headRow.appendChild( el( 'th', { text: '动作' } ) );
        }
        thead.appendChild( headRow );
        table.appendChild( thead );

        var tbody = el( 'tbody' );
        renderedRows.forEach( function ( row ) {
          var rowIndex = ( sheet.rows || [] ).indexOf( row );
          var tr = el( 'tr', { 'data-row-index': String( rowIndex ) } );
          columns.forEach( function ( column ) {
            tr.appendChild( el( 'td', {}, [
              el( 'input', {
                className: 'labworkbook-table-input',
                type: 'text',
                value: row[ column ] || '',
                'data-column': column
              } )
            ] ) );
          } );

          if ( sheet.type === 'main_log' ) {
            var shotTitle = utils.buildShotPageTitle( {
              runLabel: state.workbook.run_label,
              row: row
            } );
            var actionCell = el( 'td', { className: 'labworkbook-action-cell' } );
            var actionButton = el( 'button', {
              type: 'button',
              className: 'labworkbook-button-secondary',
              text: shotTitle ? '生成 / 更新 Shot 页面' : '补齐 Run / 日期 / No 后可生成',
              disabled: shotTitle ? null : 'disabled'
            } );
            actionButton.addEventListener( 'click', function () {
              updateDraftFromTable( table, sheet );
              persistSheet( sheet ).then( function () {
                return api.postWithToken( 'csrf', {
                  action: 'labworkbookupsertshot',
                  format: 'json',
                  slug: state.workbook.slug,
                  sheet_key: sheet.sheet_key,
                  row_index: rowIndex
                } );
              } ).then( function ( data ) {
                var payload = data.labworkbookupsertshot;
                setStatus( 'success', '已同步到 ' + payload.page_title );
                var link = createShotOpenLink( payload.page_title );
                if ( link ) {
                  actionCell.appendChild( link );
                }
              } ).catch( function ( error ) {
                setStatus( 'error', error && error.message ? error.message : '同步 Shot 页面失败。' );
              } );
            } );
            actionCell.appendChild( actionButton );
            if ( shotTitle ) {
              actionCell.appendChild( el( 'div', { className: 'labworkbook-help', text: shotTitle } ) );
              actionCell.appendChild( createShotOpenLink( shotTitle ) );
            }
            tr.appendChild( actionCell );
          }

          tbody.appendChild( tr );
        } );
        table.appendChild( tbody );
      } else if ( Array.isArray( sheet.grid ) ) {
        var gridBody = el( 'tbody' );
        ( sheet.grid || [] ).forEach( function ( row, rowIndex ) {
          var gridRow = el( 'tr', { 'data-grid-row': String( rowIndex ) } );
          ( row || [] ).forEach( function ( cell, colIndex ) {
            gridRow.appendChild( el( 'td', {}, [
              el( 'input', {
                className: 'labworkbook-table-input',
                type: 'text',
                value: cell || '',
                'data-grid-col': String( colIndex )
              } )
            ] ) );
          } );
          gridBody.appendChild( gridRow );
        } );
        table.appendChild( gridBody );
      } else {
        wrapper.appendChild( el( 'div', { className: 'labworkbook-empty', text: '当前工作表没有可渲染的数据。' } ) );
      }

      return wrapper;
    }

    function renderTabs() {
      tabs.innerHTML = '';
      panel.innerHTML = '';
      if ( !state.workbook ) {
        panel.appendChild( el( 'div', { className: 'labworkbook-empty', text: '未找到实验工作簿数据。' } ) );
        return;
      }

      var sheets = state.workbook.sheets || [];
      if ( !state.activeSheetKey && sheets.length ) {
        state.activeSheetKey = sheets[ 0 ].sheet_key;
      }

      sheets.forEach( function ( sheet ) {
        var button = el( 'button', {
          type: 'button',
          className: 'labworkbook-tab' + ( sheet.sheet_key === state.activeSheetKey ? ' is-active' : '' ),
          text: sheet.sheet_name + ' · ' + utils.formatSheetTypeLabel( sheet.type )
        } );
        button.addEventListener( 'click', function () {
          state.activeSheetKey = sheet.sheet_key;
          renderTabs();
        } );
        tabs.appendChild( button );
      } );

      var activeSheet = getDraftSheet( state.activeSheetKey );
      if ( activeSheet ) {
        panel.appendChild( renderSheetTable( activeSheet ) );
      }
    }

    function render() {
      renderToolbar();
      renderSummary();
      renderTabs();
    }

    function loadWorkbook( slug ) {
      setStatus( '', '' );
      api.get( {
        action: 'labworkbookget',
        format: 'json',
        slug: slug || ''
      } ).then( function ( data ) {
        var payload = data.labworkbookget;
        state.workbooks = payload.workbooks || [];
        state.selectedSlug = payload.selected_slug || '';
        state.workbook = payload.workbook || null;
        state.activeSheetKey = state.workbook && state.workbook.sheets && state.workbook.sheets[ 0 ] ? state.workbook.sheets[ 0 ].sheet_key : '';
        state.draftSheets = {};
        state.sheetFilters = {};
        render();
      } ).catch( function ( error ) {
        setStatus( 'error', error && error.message ? error.message : '加载实验工作簿失败。' );
      } );
    }

    loadWorkbook( state.selectedSlug );
  }

  if ( document.readyState === 'loading' ) {
    document.addEventListener( 'DOMContentLoaded', mountWorkbook );
  } else {
    mountWorkbook();
  }
}() );
