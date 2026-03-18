( function () {
  function createEl( tag, attrs, children ) {
    var el = document.createElement( tag );
    Object.entries( attrs || {} ).forEach( function ( entry ) {
      var key = entry[ 0 ];
      var value = entry[ 1 ];
      if ( value === null || value === undefined ) {
        return;
      }
      if ( key === 'className' ) {
        el.className = value;
      } else if ( key === 'text' ) {
        el.textContent = value;
      } else if ( key === 'html' ) {
        el.innerHTML = value;
      } else {
        el.setAttribute( key, value );
      }
    } );
    ( children || [] ).forEach( function ( child ) {
      if ( child ) {
        el.appendChild( child );
      }
    } );
    return el;
  }

  function createHero( config ) {
    var left = createEl( 'div', {}, [
      createEl( 'span', { className: 'labassistant-eyebrow', text: 'Knowledge Console' } ),
      createEl( 'h1', { text: '知识助手' } ),
      createEl( 'p', {
        text: '站内问题、文献对照、导师式解释和条目草稿都从这里走。助手会先检索实验室自己的条目和结构化记录，再按证据需要扩展到文献和工具结果。'
      } ),
      createEl( 'div', { className: 'labassistant-hero-list' }, [
        createEl( 'span', { text: '优先检索本组 Wiki / Cargo / Shot / SOP' } ),
        createEl( 'span', { text: '需要时再查 Zotero / PDF / 外部学术来源' } ),
        createEl( 'span', { text: '生成草稿前必须给出预览与来源' } )
      ] )
    ] );

    var meta = createEl( 'div', { className: 'labassistant-hero-meta' }, [
      createEl( 'span', { className: 'labassistant-eyebrow', text: 'Session Context' } ),
      createEl( 'dl', {}, [
        createEl( 'div', {}, [
          createEl( 'dt', { text: '当前用户' } ),
          createEl( 'dd', { text: config.userName || '未登录' } )
        ] ),
        createEl( 'div', {}, [
          createEl( 'dt', { text: '解释模式' } ),
          createEl( 'dd', { text: '入门 / 进阶 / 研究' } )
        ] ),
        createEl( 'div', {}, [
          createEl( 'dt', { text: '草稿前缀' } ),
          createEl( 'dd', { text: config.draftPrefix || '知识助手草稿' } )
        ] ),
        createEl( 'div', {}, [
          createEl( 'dt', { text: '当前页' } ),
          createEl( 'dd', { text: config.currentTitle || 'Special:LabAssistant' } )
        ] )
      ] )
    ] );

    return createEl( 'section', { className: 'labassistant-hero' }, [ left, meta ] );
  }

  function renderStepStream( container, steps ) {
    container.innerHTML = '';
    if ( !steps || !steps.length ) {
      container.appendChild( createEl( 'div', { className: 'labassistant-empty', html: '<strong>还没有步骤。</strong><span>输入一个问题后，这里会显示站内检索、文献扩搜、工具调用和证据校验过程。</span>' } ) );
      return;
    }
    steps.forEach( function ( step ) {
      container.appendChild( createEl( 'div', { className: 'labassistant-step is-' + ( step.status || 'waiting' ) }, [
        createEl( 'div', { className: 'labassistant-step-head' }, [
          createEl( 'strong', { className: 'labassistant-step-title', text: step.title || step.stage || '步骤' } ),
          createEl( 'span', { className: 'labassistant-step-state', text: step.status || 'waiting' } )
        ] ),
        createEl( 'div', { className: 'labassistant-status-note', text: step.detail || '' } )
      ] ) );
    } );
  }

  function renderResult( container, result, apiBase ) {
    container.innerHTML = '';
    if ( !result ) {
      container.appendChild( createEl( 'div', { className: 'labassistant-empty', html: '<strong>结果区待命。</strong><span>这里会显示回答、证据、待确认草稿和后续追问建议。</span>' } ) );
      return;
    }

    var answer = createEl( 'div', { className: 'labassistant-answer' } );
    answer.appendChild( createEl( 'div', { className: 'labassistant-answer-card' }, [
      createEl( 'small', { text: 'Answer' } ),
      createEl( 'h3', { text: '结论摘要' } ),
      createEl( 'p', { text: result.answer || '当前没有可展示的回答。' } )
    ] ) );

    if ( result.unresolved_gaps && result.unresolved_gaps.length ) {
      var gapList = createEl( 'div', { className: 'labassistant-gap-list' } );
      result.unresolved_gaps.forEach( function ( gap ) {
        gapList.appendChild( createEl( 'div', { className: 'labassistant-gap-card' }, [
          createEl( 'strong', { text: gap } )
        ] ) );
      } );
      answer.appendChild( gapList );
    }

    if ( result.sources && result.sources.length ) {
      var sourceCard = createEl( 'div', { className: 'labassistant-source-card' }, [
        createEl( 'small', { text: 'Evidence' } ),
        createEl( 'h3', { text: '来源与命中条目' } )
      ] );
      var sourceList = createEl( 'div', { className: 'labassistant-source-list' } );
      result.sources.forEach( function ( source ) {
        var item = createEl( 'div', {}, [
          source.url
            ? createEl( 'a', { href: source.url, target: '_blank', rel: 'noopener', text: source.title || source.source_id || '来源' } )
            : createEl( 'strong', { text: source.title || source.source_id || '来源' } ),
          createEl( 'span', {
            className: 'labassistant-source-meta',
            text: [ source.source_type, source.snippet ].filter( Boolean ).join( ' · ' )
          } )
        ] );
        sourceList.appendChild( item );
      } );
      sourceCard.appendChild( sourceList );
      answer.appendChild( sourceCard );
    }

    if ( result.suggested_followups && result.suggested_followups.length ) {
      var followCard = createEl( 'div', { className: 'labassistant-source-card' }, [
        createEl( 'small', { text: 'Next' } ),
        createEl( 'h3', { text: '继续追问建议' } )
      ] );
      var followList = createEl( 'div', { className: 'labassistant-followup-list' } );
      result.suggested_followups.forEach( function ( item ) {
        followList.appendChild( createEl( 'button', {
          type: 'button',
          className: 'labassistant-chip',
          text: item
        } ) );
      } );
      followCard.appendChild( followList );
      answer.appendChild( followCard );
    }

    if ( result.draft_preview ) {
      var draftCard = createEl( 'div', { className: 'labassistant-draft-card' }, [
        createEl( 'small', { text: 'Draft Preview' } ),
        createEl( 'h3', { text: result.draft_preview.title || '草稿预览' } ),
        createEl( 'div', { className: 'labassistant-callout', text: '这只是预览。点击提交后，系统才会创建站内草稿页。' } ),
        createEl( 'div', { className: 'labassistant-code', text: result.draft_preview.content || '' } )
      ] );
      var draftActions = createEl( 'div', { className: 'labassistant-draft-actions' } );
      var commitButton = createEl( 'button', {
        type: 'button',
        className: 'labassistant-button',
        text: '提交到草稿页'
      } );
      commitButton.addEventListener( 'click', function () {
        commitButton.disabled = true;
        fetch( apiBase + '/draft/commit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify( {
            preview_id: result.draft_preview.preview_id
          } )
        } ).then( function ( response ) {
          return response.json().then( function ( body ) {
            if ( !response.ok ) {
              throw new Error( body.detail || '提交失败' );
            }
            alert( '已写入：' + body.page_title );
          } );
        } ).catch( function ( error ) {
          alert( error.message || '提交失败' );
        } ).finally( function () {
          commitButton.disabled = false;
        } );
      } );
      draftActions.appendChild( commitButton );
      draftCard.appendChild( draftActions );
      answer.appendChild( draftCard );
    }

    container.appendChild( answer );
  }

  function mountApp() {
    var root = document.getElementById( 'labassistant-root' );
    if ( !root || !window.mw ) {
      return;
    }

    var config = mw.config.get( 'wgLabAssistant' ) || {};
    var apiBase = config.apiBase || '/tools/assistant/api';

    var app = createEl( 'div', { className: 'labassistant-app' } );
    app.appendChild( createHero( config ) );

    var questionInput = createEl( 'textarea', {
      placeholder: '例如：请比较 TNSA 和 RPA 的主导驱动场，并结合本组 TPS / RCF 读谱说明如何区分。'
    } );
    if ( config.seedQuestion ) {
      questionInput.value = config.seedQuestion;
    }
    var modeSelect = createEl( 'select', {}, [
      createEl( 'option', { value: 'qa', text: '问答' } ),
      createEl( 'option', { value: 'compare', text: '对照' } ),
      createEl( 'option', { value: 'draft', text: '草稿生成' } )
    ] );
    var detailSelect = createEl( 'select', {}, [
      createEl( 'option', { value: 'intro', text: '入门' } ),
      createEl( 'option', { value: 'intermediate', text: '进阶' } ),
      createEl( 'option', { value: 'research', text: '研究' } )
    ] );
    var contextInput = createEl( 'input', {
      type: 'text',
      value: config.currentTitle || '',
      placeholder: '可选：Theory:RPA / Shot:2026-03-14-Run01-Shot001'
    } );

    var stepContainer = createEl( 'div', { className: 'labassistant-steps' } );
    var resultContainer = createEl( 'div' );
    renderStepStream( stepContainer, [] );
    renderResult( resultContainer, null, apiBase );

    var submitButton = createEl( 'button', { type: 'button', className: 'labassistant-button', text: '启动助手循环' } );
    var resetButton = createEl( 'button', { type: 'button', className: 'labassistant-button-secondary', text: '清空当前会话' } );

    submitButton.addEventListener( 'click', function () {
      var payload = {
        question: questionInput.value.trim(),
        mode: modeSelect.value,
        detail_level: detailSelect.value,
        context_pages: contextInput.value ? [ contextInput.value ] : []
      };
      if ( !payload.question ) {
        alert( '请输入问题。' );
        return;
      }
      submitButton.disabled = true;
      renderStepStream( stepContainer, [
        { title: '准备请求', status: 'running', detail: '正在提交给 assistant_api。' }
      ] );
      fetch( apiBase + '/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify( payload )
      } ).then( function ( response ) {
        return response.json().then( function ( body ) {
          if ( !response.ok ) {
            throw new Error( body.detail || '请求失败' );
          }
          return body;
        } );
      } ).then( function ( body ) {
        renderStepStream( stepContainer, body.step_stream || [] );
        renderResult( resultContainer, body, apiBase );
      } ).catch( function ( error ) {
        renderStepStream( stepContainer, [
          { title: '助手循环中断', status: 'waiting', detail: error.message || '未知错误' }
        ] );
        renderResult( resultContainer, {
          answer: '当前请求没有完成。请先检查 assistant_api 是否已启动，以及当前问题是否超出已接入的数据源。',
          unresolved_gaps: [ error.message || '未知错误' ]
        }, apiBase );
      } ).finally( function () {
        submitButton.disabled = false;
      } );
    } );

    resetButton.addEventListener( 'click', function () {
      questionInput.value = '';
      renderStepStream( stepContainer, [] );
      renderResult( resultContainer, null, apiBase );
    } );

    var leftPanel = createEl( 'section', { className: 'labassistant-panel' }, [
      createEl( 'small', { text: 'Loop Input' } ),
      createEl( 'h2', { text: '提问与解释模式' } ),
      createEl( 'form', { className: 'labassistant-form' }, [
        createEl( 'label', {}, [
          createEl( 'span', { text: '问题' } ),
          questionInput
        ] ),
        createEl( 'div', { className: 'labassistant-form-row' }, [
          createEl( 'label', {}, [
            createEl( 'span', { text: '模式' } ),
            modeSelect
          ] ),
          createEl( 'label', {}, [
            createEl( 'span', { text: '解释层级' } ),
            detailSelect
          ] ),
          createEl( 'label', {}, [
            createEl( 'span', { text: '关联页面' } ),
            contextInput
          ] )
        ] ),
        createEl( 'div', { className: 'labassistant-toolbar' }, [
          createEl( 'span', { className: 'labassistant-status-note', text: '内部会先查站内页面、Cargo 和术语，再视证据情况扩到文献、外部学术来源与分析工具。' } ),
          createEl( 'div', { className: 'labassistant-button-row' }, [ submitButton, resetButton ] )
        ] )
      ] )
    ] );

    var rightPanel = createEl( 'div', { className: 'labassistant-answer' }, [
      createEl( 'section', { className: 'labassistant-panel' }, [
        createEl( 'small', { text: 'Step Stream' } ),
        createEl( 'h2', { text: '可视化步骤流' } ),
        stepContainer
      ] ),
      createEl( 'section', { className: 'labassistant-panel' }, [
        createEl( 'small', { text: 'Result' } ),
        createEl( 'h2', { text: '回答、证据与草稿' } ),
        resultContainer
      ] )
    ] );

    app.appendChild( createEl( 'div', { className: 'labassistant-grid' }, [ leftPanel, rightPanel ] ) );
    root.appendChild( app );
  }

  if ( document.readyState === 'loading' ) {
    document.addEventListener( 'DOMContentLoaded', mountApp );
  } else {
    mountApp();
  }
}() );

