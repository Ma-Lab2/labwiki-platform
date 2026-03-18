( function () {
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
    var root = document.getElementById( 'labassistant-admin-root' );
    if ( !root || !window.mw ) {
      return;
    }
    var config = mw.config.get( 'wgLabAssistantAdmin' ) || {};
    var apiBase = config.apiBase || '/tools/assistant/api';

    var metrics = el( 'div', { className: 'labassistant-admin-metrics' } );
    var statsPanel = el( 'section', { className: 'labassistant-panel' }, [
      el( 'small', { text: 'Assistant Health' } ),
      el( 'h2', { text: '助手运行面板' } ),
      metrics
    ] );

    var jobsPanel = el( 'section', { className: 'labassistant-panel' }, [
      el( 'small', { text: 'Reindex' } ),
      el( 'h2', { text: '索引与同步' } )
    ] );

    [ [ '重建 Wiki 索引', '/reindex/wiki' ], [ '重建 Zotero 索引', '/reindex/zotero' ] ].forEach( function ( job ) {
      var button = el( 'button', { type: 'button', className: 'labassistant-button-secondary', text: job[ 0 ] } );
      button.addEventListener( 'click', function () {
        button.disabled = true;
        fetch( apiBase + job[ 1 ], {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify( {} )
        } ).then( function ( response ) {
          return response.json().then( function ( body ) {
            if ( !response.ok ) {
              throw new Error( body.detail || '任务创建失败' );
            }
            alert( '已创建任务：' + body.job_id );
          } );
        } ).catch( function ( error ) {
          alert( error.message || '任务创建失败' );
        } ).finally( function () {
          button.disabled = false;
        } );
      } );
      jobsPanel.appendChild( button );
    } );

    function renderStats( stats ) {
      metrics.innerHTML = '';
      [
        [ '会话数', stats.sessions_total || 0 ],
        [ '轮次总数', stats.turns_total || 0 ],
        [ '文档块', stats.chunks_total || 0 ],
        [ '待处理任务', stats.pending_jobs || 0 ]
      ].forEach( function ( entry ) {
        metrics.appendChild( el( 'div', { className: 'labassistant-admin-metric' }, [
          el( 'small', { text: entry[ 0 ] } ),
          el( 'strong', { text: String( entry[ 1 ] ) } )
        ] ) );
      } );
    }

    fetch( apiBase + '/admin/stats', { credentials: 'same-origin' } )
      .then( function ( response ) { return response.json(); } )
      .then( renderStats )
      .catch( function () {
        metrics.appendChild( el( 'div', { className: 'labassistant-empty', html: '<strong>统计暂不可用。</strong><span>请确认 assistant_api 与 assistant_store 已启动。</span>' } ) );
      } );

    root.appendChild( el( 'div', { className: 'labassistant-app' }, [ statsPanel, jobsPanel ] ) );
  }

  if ( document.readyState === 'loading' ) {
    document.addEventListener( 'DOMContentLoaded', mountAdmin );
  } else {
    mountAdmin();
  }
}() );

