( function () {
  function getEditorUtils() {
    return window.LabAssistantEditorUtils || ( window.mw && mw.labassistantEditorUtils ) || null;
  }

  function getDraftHandoffStorageKey( title, host ) {
    var editorUtils = getEditorUtils();
    if ( editorUtils && editorUtils.buildDraftHandoffStorageKey ) {
      return editorUtils.buildDraftHandoffStorageKey( title, host );
    }
    return 'labassistant-draft-handoff::' + String( host || '' ) + '::' + String( title || '' );
  }

  function ensureConfig() {
    return window.mw && mw.config && mw.config.get( 'wgLabAssistant' );
  }

  function openDrawerWithSeed( config, question ) {
    mw.loader.using( 'ext.labassistant.ui' ).then( function () {
      if ( mw.labassistantUI && mw.labassistantUI.mountDrawer ) {
        var controller = mw.labassistantUI.mountDrawer( document.body, config );
        if ( controller && controller.setQuestion ) {
          controller.setQuestion( question );
        }
        if ( controller && controller.open ) {
          controller.open();
        }
      }
    } ).catch( function ( error ) {
      console.warn( error );
    } );
  }

  function createHelperBar( className, titleText, descriptionText, buttonText, onClick ) {
    var helper = document.createElement( 'div' );
    helper.className = className;

    var copy = document.createElement( 'div' );
    copy.className = 'labassistant-editor-helper-copy';
    copy.innerHTML = '<strong>' + titleText + '</strong><span>' + descriptionText + '</span>';

    var button = document.createElement( 'button' );
    button.type = 'button';
    button.className = 'labassistant-editor-helper-button';
    button.textContent = buttonText;
    button.addEventListener( 'click', onClick );

    helper.appendChild( copy );
    helper.appendChild( button );
    return helper;
  }

  function buildFormSeedQuestion( config ) {
    var formContext = config.formContext || {};
    var formName = formContext.formName || '当前表单';
    var fieldMap = {
      '术语条目': [ '中文名', '英文名', '缩写', '摘要', '别名', '关联页面', '来源' ],
      '设备条目': [ '设备名称', '系统归属', '关键参数', '用途', '运行页', '来源' ],
      '诊断条目': [ '诊断名称', '测量对象', '主要输出', '易错点', '工具入口', '来源' ],
      '文献导读': [ '标题', '作者', '年份', 'DOI', '摘要', '相关页面', '来源' ]
    };
    var fields = fieldMap[ formName ] || [];
    return '请根据当前页面和表单上下文，为“' + formName + '”生成结构化字段建议。' +
      '只输出字段建议，每行一个“字段名：值”，不要写额外说明。' +
      '如果某字段无法从当前证据确认，请留空，不要写“待补充”“未知”“无”“表单上下文”。' +
      '最后单独补一行“缺失字段：...”。' +
      ( fields.length ? '字段仅限：' + fields.join( '、' ) + '。' : '' );
  }

  function ensureLauncherButton( config ) {
    if ( document.querySelector( '.labassistant-launcher-button' ) ) {
      return;
    }
    var button = document.createElement( 'button' );
    button.type = 'button';
    button.className = 'labassistant-launcher-button';
    button.setAttribute( 'aria-label', '打开知识助手' );
    button.innerHTML = '<span class="labassistant-launcher-dot"></span><span>知识助手</span>';
    button.addEventListener( 'click', function () {
      mw.loader.using( 'ext.labassistant.ui' ).then( function () {
        if ( mw.labassistantUI && mw.labassistantUI.mountDrawer ) {
          mw.labassistantUI.mountDrawer( document.body, config ).open();
        }
      } ).catch( function ( error ) {
        console.warn( error );
      } );
    } );
    document.body.appendChild( button );
  }

  function ensureEditorHelperButton( config ) {
    var textarea = document.getElementById( 'wpTextbox1' );
    if ( !textarea || document.querySelector( '.labassistant-editor-helper' ) ) {
      return;
    }

    var helper = createHelperBar(
      'labassistant-editor-helper',
      '知识助手填充',
      '先让助手整理草稿，再回填到编辑框；不会自动保存页面。',
      '用知识助手整理并填充',
      function () {
        openDrawerWithSeed(
          config,
          '请把当前页面整理成可直接填入编辑框的页面草稿，并保留 wiki 标题结构'
        );
      }
    );
    textarea.parentNode.insertBefore( helper, textarea );
  }

  function applyDraftHandoffToSourceEditor( config ) {
    var textarea = document.getElementById( 'wpTextbox1' );
    var title = config.defaultContextTitle || config.currentTitle || '';
    var key;
    var raw;
    var payload;
    var helper;
    var notice;

    if ( !textarea || !title || !window.sessionStorage ) {
      return;
    }

    key = getDraftHandoffStorageKey( title, window.location.host );
    raw = sessionStorage.getItem( key );
    if ( !raw ) {
      return;
    }

    sessionStorage.removeItem( key );
    try {
      payload = JSON.parse( raw );
    } catch ( error ) {
      return;
    }

    if ( !payload || !payload.content ) {
      return;
    }

    textarea.value = payload.content;
    textarea.dispatchEvent( new Event( 'input', { bubbles: true } ) );
    textarea.dispatchEvent( new Event( 'change', { bubbles: true } ) );
    textarea.focus();
    textarea.scrollTop = 0;

    helper = document.querySelector( '.labassistant-editor-helper' );
    if ( !helper ) {
      return;
    }
    notice = document.createElement( 'div' );
    notice.className = 'labassistant-callout labassistant-editor-handoff-notice';
    notice.textContent = '已从可视化编辑页带入草稿，页面尚未保存。';
    helper.appendChild( notice );
  }

  function ensurePageFormsHelperButton( config ) {
    var form = document.querySelector( '#pfForm, form[action*="Special:FormEdit"], form[action*="action=formedit"]' );
    if ( !form || document.querySelector( '.labassistant-pageforms-helper' ) ) {
      return;
    }
    form.parentNode.insertBefore( createHelperBar(
      'labassistant-editor-helper labassistant-pageforms-helper',
      '知识助手填表',
      '先生成字段建议，再按匹配结果填入表单；不会自动提交。',
      '用知识助手生成字段建议',
      function () {
        openDrawerWithSeed( config, buildFormSeedQuestion( config ) );
      }
    ), form );
  }

  function ensureVisualEditorHelperButton( config ) {
    var anchor = document.querySelector(
      '.ve-ui-toolbar, .ve-init-mw-desktopArticleTarget-toolbar, .ve-init-mw-target, .mw-body-content'
    );
    if ( !anchor || document.querySelector( '.labassistant-ve-helper' ) ) {
      return;
    }
    anchor.parentNode.insertBefore( createHelperBar(
      'labassistant-editor-helper labassistant-ve-helper',
      '知识助手生成草稿',
      '先生成页面草稿，再切到源码编辑预填；不会自动发布页面。',
      '用知识助手生成草稿',
      function () {
        openDrawerWithSeed(
          config,
          '请基于当前页面生成一版可发布的页面草稿，并保留 wiki 标题结构；我会切到源码编辑再填入，不要直接写入页面。'
        );
      }
    ), anchor );
  }

  function mountSpecialWorkspace( config ) {
    var root = document.getElementById( 'labassistant-root' );
    if ( !root || root.dataset.labassistantMounted === 'true' ) {
      return;
    }
    mw.loader.using( 'ext.labassistant.ui' ).then( function () {
      if ( mw.labassistantUI && mw.labassistantUI.mountSpecial ) {
        mw.labassistantUI.mountSpecial( root, config );
      }
    } ).catch( function ( error ) {
      console.warn( error );
    } );
  }

  function init() {
    var config = ensureConfig();
    var editorUtils = getEditorUtils();
    var editorMode;
    if ( !config ) {
      return;
    }
    editorMode = editorUtils && editorUtils.detectEditorMode ? editorUtils.detectEditorMode( config ) : config.editorMode;

    if ( config.mountMode === 'special' ) {
      mountSpecialWorkspace( config );
      return;
    }

    ensureLauncherButton( config );
    if ( editorMode === 'source_edit' ) {
      ensureEditorHelperButton( config );
      applyDraftHandoffToSourceEditor( config );
      return;
    }
    if ( editorMode === 'pageforms_edit' ) {
      ensurePageFormsHelperButton( config );
      return;
    }
    if ( editorMode === 'visual_editor' ) {
      ensureVisualEditorHelperButton( config );
    }
  }

  if ( document.readyState === 'loading' ) {
    document.addEventListener( 'DOMContentLoaded', init );
  } else {
    init();
  }
}() );
