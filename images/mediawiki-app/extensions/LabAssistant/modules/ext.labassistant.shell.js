( function () {
  function getEditorUtils() {
    return window.LabAssistantEditorUtils || ( window.mw && mw.labassistantEditorUtils ) || null;
  }

  function getAttachmentUtils() {
    return window.LabAssistantAttachmentUtils || ( window.mw && mw.labassistantAttachmentUtils ) || null;
  }

  function getPdfReaderUtils() {
    return window.LabAssistantPdfReaderUtils || ( window.mw && mw.labassistantPdfReaderUtils ) || null;
  }

  function getEditorUploadUtils() {
    return window.LabAssistantEditorUploadUtils || ( window.mw && mw.labassistantEditorUploadUtils ) || null;
  }

  function getDraftHandoffStorageKey( title, host ) {
    var editorUtils = getEditorUtils();
    if ( editorUtils && editorUtils.buildDraftHandoffStorageKey ) {
      return editorUtils.buildDraftHandoffStorageKey( title, host );
    }
    return 'labassistant-draft-handoff::' + String( host || '' ) + '::' + String( title || '' );
  }

  function getSubmissionGuidanceStorageKey( title, host ) {
    var editorUtils = getEditorUtils();
    if ( editorUtils && editorUtils.buildSubmissionGuidanceStorageKey ) {
      return editorUtils.buildSubmissionGuidanceStorageKey( title, host );
    }
    return 'labassistant-submission-guidance::' + String( host || '' ) + '::' + String( title || '' );
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

  function resolvePdfReaderSourceFromNode( node, config ) {
    var utils = getPdfReaderUtils();
    var sourceType;
    var fileTitle;
    var normalized;
    if ( !node || !utils || !utils.normalizePdfReaderSource ) {
      return null;
    }
    sourceType = String( node.dataset.sourceType || '' ).trim() || 'wiki_file';
    fileTitle = String( node.dataset.fileTitle || '' ).trim();
    normalized = utils.normalizePdfReaderSource( {
      type: sourceType,
      fileTitle: fileTitle,
      url: sourceType === 'wiki_file' && utils.buildWikiFileRedirectUrl ? utils.buildWikiFileRedirectUrl( fileTitle, mw ) : '',
      fileLabel: node.dataset.fileLabel || fileTitle,
      pageTitle: node.dataset.pageTitle || config.currentTitle || config.defaultContextTitle || ''
    } );
    return normalized;
  }

  function buildPdfViewerUrl( sourceUrl, pageNumber, zoomPercent ) {
    var hash = '#page=' + String( pageNumber || 1 );
    if ( zoomPercent ) {
      hash += '&zoom=' + String( zoomPercent );
    }
    return String( sourceUrl || '' ).replace( /#.*$/, '' ) + hash;
  }

  function importClipboardSelection( textarea ) {
    if ( !navigator.clipboard || typeof navigator.clipboard.readText !== 'function' ) {
      return Promise.reject( new Error( '当前浏览器不支持读取剪贴板文本' ) );
    }
    return navigator.clipboard.readText().then( function ( value ) {
      textarea.value = String( value || '' ).trim();
      textarea.dispatchEvent( new Event( 'input', { bubbles: true } ) );
      return textarea.value;
    } );
  }

  function createPdfReaderPanel( config, source, options ) {
    var utils = getPdfReaderUtils();
    var editUrl = utils && utils.buildLiteratureGuideEditUrl ?
      utils.buildLiteratureGuideEditUrl( source.pageTitle || config.currentTitle || '', mw ) :
      '';
    var state = {
      pageNumber: 1,
      zoomPercent: 110
    };
    var container = document.createElement( 'section' );
    var shellClassName = options && options.floating ?
      'labassistant-pdf-reader-shell is-floating' :
      'labassistant-pdf-reader-shell';
    var toolbar = document.createElement( 'div' );
    var titleBlock = document.createElement( 'div' );
    var controlBlock = document.createElement( 'div' );
    var body = document.createElement( 'div' );
    var frameWrap = document.createElement( 'div' );
    var quoteWrap = document.createElement( 'div' );
    var actionRow = document.createElement( 'div' );
    var frame = document.createElement( 'iframe' );
    var prevButton = document.createElement( 'button' );
    var nextButton = document.createElement( 'button' );
    var pageInput = document.createElement( 'input' );
    var zoomSelect = document.createElement( 'select' );
    var downloadLink = document.createElement( 'a' );
    var editLink = editUrl ? document.createElement( 'a' ) : null;
    var fullscreenButton = document.createElement( 'button' );
    var clipboardButton = document.createElement( 'button' );
    var sendButton = document.createElement( 'button' );
    var closeButton = options && options.floating ? document.createElement( 'button' ) : null;
    var quoteArea = document.createElement( 'textarea' );
    var statusNode = document.createElement( 'div' );

    function setStatus( message, kind ) {
      statusNode.textContent = message;
      statusNode.className = 'labassistant-pdf-reader-status' + ( kind ? ' is-' + kind : '' );
    }

    function refreshFrame() {
      frame.src = buildPdfViewerUrl( source.url, state.pageNumber, state.zoomPercent );
    }

    container.className = shellClassName;
    toolbar.className = 'labassistant-pdf-reader-toolbar';
    var titleStrong = document.createElement( 'strong' );
    var titleMeta = document.createElement( 'span' );
    var quoteCopy = document.createElement( 'div' );
    var quoteStrong = document.createElement( 'strong' );
    var quoteMeta = document.createElement( 'span' );
    titleBlock.className = 'labassistant-pdf-reader-title';
    controlBlock.className = 'labassistant-pdf-reader-controls';
    body.className = 'labassistant-pdf-reader-body';
    frameWrap.className = 'labassistant-pdf-reader-frame-wrap';
    quoteWrap.className = 'labassistant-pdf-reader-quote';
    frame.className = 'labassistant-pdf-reader-frame';
    frame.setAttribute( 'title', source.fileLabel || 'PDF 阅读器' );
    frame.setAttribute( 'loading', 'lazy' );
    frameWrap.appendChild( frame );

    titleStrong.textContent = 'PDF 阅读';
    titleMeta.textContent = String( source.fileLabel || '未命名 PDF' );
    titleBlock.appendChild( titleStrong );
    titleBlock.appendChild( titleMeta );

    pageInput.type = 'number';
    pageInput.min = '1';
    pageInput.value = '1';
    pageInput.className = 'labassistant-pdf-reader-page';
    pageInput.setAttribute( 'aria-label', 'PDF 页码' );
    pageInput.addEventListener( 'change', function () {
      state.pageNumber = utils && utils.clampPdfPageNumber ?
        utils.clampPdfPageNumber( pageInput.value, 0 ) :
        Math.max( 1, Number( pageInput.value || 1 ) );
      pageInput.value = String( state.pageNumber );
      refreshFrame();
    } );

    prevButton.type = 'button';
    prevButton.className = 'labassistant-pdf-reader-button';
    prevButton.textContent = '上一页';
    prevButton.addEventListener( 'click', function () {
      state.pageNumber = utils && utils.clampPdfPageNumber ?
        utils.clampPdfPageNumber( state.pageNumber, -1 ) :
        Math.max( 1, state.pageNumber - 1 );
      pageInput.value = String( state.pageNumber );
      refreshFrame();
    } );

    nextButton.type = 'button';
    nextButton.className = 'labassistant-pdf-reader-button';
    nextButton.textContent = '下一页';
    nextButton.addEventListener( 'click', function () {
      state.pageNumber = utils && utils.clampPdfPageNumber ?
        utils.clampPdfPageNumber( state.pageNumber, 1 ) :
        Math.max( 1, state.pageNumber + 1 );
      pageInput.value = String( state.pageNumber );
      refreshFrame();
    } );

    [ 90, 100, 110, 125, 150 ].forEach( function ( value ) {
      var option = document.createElement( 'option' );
      option.value = String( value );
      option.textContent = value + '%';
      if ( value === state.zoomPercent ) {
        option.selected = true;
      }
      zoomSelect.appendChild( option );
    } );
    zoomSelect.className = 'labassistant-pdf-reader-zoom';
    zoomSelect.addEventListener( 'change', function () {
      state.zoomPercent = Number( zoomSelect.value || 110 );
      refreshFrame();
    } );

    downloadLink.className = 'labassistant-pdf-reader-button is-link';
    downloadLink.href = source.url;
    downloadLink.target = '_blank';
    downloadLink.rel = 'noopener';
    downloadLink.textContent = '打开 / 下载';

    if ( editLink ) {
      editLink.className = 'labassistant-pdf-reader-button is-link';
      editLink.href = editUrl;
      editLink.textContent = '编辑条目';
    }

    fullscreenButton.type = 'button';
    fullscreenButton.className = 'labassistant-pdf-reader-button';
    fullscreenButton.textContent = '全屏';
    fullscreenButton.addEventListener( 'click', function () {
      if ( document.fullscreenElement === container && document.exitFullscreen ) {
        document.exitFullscreen();
        return;
      }
      if ( container.requestFullscreen ) {
        container.requestFullscreen().catch( function () {} );
      }
    } );

    if ( closeButton ) {
      closeButton.type = 'button';
      closeButton.className = 'labassistant-pdf-reader-button';
      closeButton.textContent = '关闭';
      closeButton.addEventListener( 'click', function () {
        container.hidden = true;
      } );
    }

    controlBlock.appendChild( prevButton );
    controlBlock.appendChild( pageInput );
    controlBlock.appendChild( nextButton );
    controlBlock.appendChild( zoomSelect );
    controlBlock.appendChild( downloadLink );
    if ( editLink ) {
      controlBlock.appendChild( editLink );
    }
    controlBlock.appendChild( fullscreenButton );
    if ( closeButton ) {
      controlBlock.appendChild( closeButton );
    }
    toolbar.appendChild( titleBlock );
    toolbar.appendChild( controlBlock );

    quoteArea.className = 'labassistant-pdf-reader-quote-input';
    quoteArea.rows = 7;
    quoteArea.placeholder = '从 PDF 中复制一段文本到这里，再发给助手继续问答。';

    clipboardButton.type = 'button';
    clipboardButton.className = 'labassistant-pdf-reader-button';
    clipboardButton.textContent = '粘贴当前摘录';
    clipboardButton.addEventListener( 'click', function () {
      importClipboardSelection( quoteArea ).then( function ( value ) {
        setStatus( value ? '已从剪贴板带入摘录。' : '剪贴板里没有可用文本。', value ? 'success' : 'warning' );
      } ).catch( function ( error ) {
        setStatus( String( error && error.message ? error.message : '读取剪贴板失败' ), 'error' );
      } );
    } );

    sendButton.type = 'button';
    sendButton.className = 'labassistant-pdf-reader-button is-primary';
    sendButton.textContent = '发送摘录到助手';
    sendButton.addEventListener( 'click', function () {
      var selectedText = String( quoteArea.value || '' ).trim();
      if ( !selectedText ) {
        setStatus( '请先在阅读后粘贴一段 PDF 摘录。', 'warning' );
        quoteArea.focus();
        return;
      }
      if ( !utils || !utils.buildAssistantQuotePrompt ) {
        setStatus( 'PDF 阅读器工具未加载，暂时无法发送摘录。', 'error' );
        return;
      }
      openDrawerWithSeed( config, utils.buildAssistantQuotePrompt( {
        pageTitle: source.pageTitle || config.currentTitle || config.defaultContextTitle || '',
        fileLabel: source.fileLabel,
        pageNumber: state.pageNumber,
        selectedText: selectedText
      } ) );
      setStatus( '已把当前摘录送到知识助手。', 'success' );
    } );

    quoteCopy.className = 'labassistant-pdf-reader-copy';
    quoteStrong.textContent = '选区引用问答';
    quoteMeta.textContent = '当前版本先支持阅读、复制摘录和带页码送给助手，不直接做整篇 PDF 问答。';
    quoteCopy.appendChild( quoteStrong );
    quoteCopy.appendChild( quoteMeta );
    quoteWrap.appendChild( quoteCopy );
    quoteWrap.appendChild( quoteArea );
    actionRow.className = 'labassistant-pdf-reader-inline-actions';
    actionRow.appendChild( clipboardButton );
    actionRow.appendChild( sendButton );
    quoteWrap.appendChild( actionRow );
    quoteWrap.appendChild( statusNode );

    body.appendChild( frameWrap );
    body.appendChild( quoteWrap );
    container.appendChild( toolbar );
    container.appendChild( body );
    refreshFrame();
    setStatus( '已载入 PDF 阅读器。', 'success' );
    return container;
  }

  function ensureFloatingPdfReader( config, source ) {
    var root = document.querySelector( '.labassistant-pdf-reader-floating-root' );
    var panel;
    if ( !root ) {
      root = document.createElement( 'div' );
      root.className = 'labassistant-pdf-reader-floating-root';
      document.body.appendChild( root );
    }
    root.hidden = false;
    root.innerHTML = '';
    panel = createPdfReaderPanel( config, source, { floating: true } );
    root.appendChild( panel );
    return root;
  }

  function ensureLiteratureGuidePdfReader( config ) {
    var utils = getPdfReaderUtils();
    var emptyNode = document.querySelector( '.labassistant-pdf-reader-empty' );
    var sourceNode = document.querySelector( '.labassistant-pdf-reader-source' );
    var source;
    var panel;
    var editLink;
    if ( !utils || !utils.isLiteratureGuideTitle || !utils.isLiteratureGuideTitle( config.currentTitle ) ) {
      return;
    }
    if ( emptyNode && emptyNode.dataset.labassistantMounted !== 'true' ) {
      editLink = utils.buildLiteratureGuideEditUrl ?
        utils.buildLiteratureGuideEditUrl( config.currentTitle || '', mw ) :
        '';
      if ( editLink ) {
        var action = document.createElement( 'a' );
        action.className = 'labassistant-pdf-reader-button is-link';
        action.href = editLink;
        action.textContent = '编辑条目并关联 PDF';
        emptyNode.appendChild( action );
      }
      emptyNode.dataset.labassistantMounted = 'true';
    }
    if ( !sourceNode || sourceNode.dataset.labassistantMounted === 'true' ) {
      return;
    }
    source = resolvePdfReaderSourceFromNode( sourceNode, config );
    if ( !source ) {
      return;
    }
    panel = createPdfReaderPanel( config, source, { floating: false } );
    sourceNode.dataset.labassistantMounted = 'true';
    sourceNode.appendChild( panel );
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
      '文献导读': [ '标题', '作者', '年份', 'DOI', 'PDF文件', '摘要', '相关页面', '来源' ],
      'Shot记录': [ '日期', 'Run', '实验目标', 'TPS结果图', 'RCF结果截图', '主要观测', '判断依据', '周实验日志', '处理结果文件', '原始数据主目录' ]
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
    var helper;
    var copy;
    if ( !textarea || document.querySelector( '.labassistant-editor-helper' ) ) {
      return;
    }

    helper = createHelperBar(
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
    copy = helper.querySelector( '.labassistant-editor-helper-copy span' );
    if ( copy ) {
      copy.textContent = '先让助手整理草稿，再回填到编辑框；也可以直接粘贴截图，自动上传到 Wiki 并插入文件语法。';
    }
    textarea.parentNode.insertBefore( helper, textarea );
  }

  function getSourceEditorStatusNotice() {
    return document.querySelector( '.labassistant-editor-upload-notice' );
  }

  function setSourceEditorStatus( message, kind ) {
    var helper = document.querySelector( '.labassistant-editor-helper' );
    var notice = getSourceEditorStatusNotice();
    if ( !helper ) {
      return;
    }
    if ( !notice ) {
      notice = document.createElement( 'div' );
      notice.className = 'labassistant-callout labassistant-editor-upload-notice';
      helper.appendChild( notice );
    }
    notice.textContent = message;
    notice.classList.toggle( 'is-pending', kind === 'pending' );
    notice.classList.toggle( 'is-error', kind === 'error' );
    notice.classList.toggle( 'is-success', kind === 'success' );
  }

  function clearSourceEditorStatus() {
    var notice = getSourceEditorStatusNotice();
    if ( notice && notice.parentNode ) {
      notice.parentNode.removeChild( notice );
    }
  }

  function getSubmitChecklistNotice() {
    return document.querySelector( '.labassistant-submit-checklist' );
  }

  function clearSubmitChecklistNotice() {
    var notice = getSubmitChecklistNotice();
    if ( notice && notice.parentNode ) {
      notice.parentNode.removeChild( notice );
    }
  }

  function getSubmitChecklistAnchor( editorMode ) {
    var form;
    var button;
    if ( editorMode === 'source_edit' ) {
      button = document.querySelector( '#wpSave, button[name="wpSave"], input[name="wpSave"]' );
      if ( button ) {
        return button.closest( '.editButtons, .wikiEditor-ui-controls, .mw-editButtons, fieldset' ) || button;
      }
      return document.querySelector( '.labassistant-editor-helper' );
    }
    if ( editorMode === 'pageforms_edit' ) {
      form = document.querySelector( '#pfForm, form[action*="Special:FormEdit"], form[action*="action=formedit"]' );
      if ( !form ) {
        return document.querySelector( '.labassistant-pageforms-helper' );
      }
      button = form.querySelector( 'button[name="wpSave"], input[name="wpSave"], button[type="submit"], input[type="submit"]' );
      if ( button ) {
        return button.closest( '.editButtons, .pfFormButtons, fieldset, p' ) || button;
      }
      return form;
    }
    return null;
  }

  function setSubmitChecklistNotice( config, detail ) {
    var editorUtils = getEditorUtils();
    var editorMode = editorUtils && editorUtils.detectEditorMode ? editorUtils.detectEditorMode( config ) : config.editorMode;
    var pendingItems = Array.isArray( detail && detail.pendingItems ) ? detail.pendingItems : [];
    var missingItems = Array.isArray( detail && detail.missingItems ) ? detail.missingItems : [];
    var preface = String(
      ( detail && ( detail.formFillNotice || detail.editorFillNotice ) ) ||
      ''
    ).trim();
    var checklistSections = editorUtils && editorUtils.buildSubmissionChecklistSections ?
      editorUtils.buildSubmissionChecklistSections( pendingItems, missingItems, { preface: preface } ) :
      null;
    var summaryText = checklistSections && checklistSections.summaryText ?
      checklistSections.summaryText :
      ( editorUtils && editorUtils.buildSubmissionChecklistNotice ?
        editorUtils.buildSubmissionChecklistNotice( missingItems, { preface: preface } ) :
        '' );
    var anchor;
    var notice;
    var copy;
    var section;
    var chipList;

    if ( ( editorMode !== 'source_edit' && editorMode !== 'pageforms_edit' ) || !summaryText ) {
      clearSubmitChecklistNotice();
      return;
    }

    anchor = getSubmitChecklistAnchor( editorMode );
    if ( !anchor || !anchor.parentNode ) {
      return;
    }

    notice = getSubmitChecklistNotice();
    if ( !notice ) {
      notice = document.createElement( 'section' );
      notice.className = 'labassistant-callout labassistant-submit-checklist';
    }
    if ( notice.parentNode !== anchor.parentNode || notice.nextSibling !== anchor ) {
      anchor.parentNode.insertBefore( notice, anchor );
    }

    notice.innerHTML = '';
    copy = document.createElement( 'div' );
    copy.className = 'labassistant-submit-checklist-copy';
    ( function () {
      var titleNode = document.createElement( 'strong' );
      var textNode = document.createElement( 'span' );
      titleNode.textContent = '提交前请确认';
      textNode.textContent = summaryText;
      copy.appendChild( titleNode );
      copy.appendChild( textNode );
    }() );
    notice.appendChild( copy );

    function appendChecklistSection( title, description, items ) {
      var head;
      var itemNode;
      var itemCopy;
      var reasonNode;
      var titleNode;
      var descriptionNode;
      if ( !items.length ) {
        return;
      }
      section = document.createElement( 'section' );
      section.className = 'labassistant-form-missing';
      head = document.createElement( 'div' );
      head.className = 'labassistant-form-missing-head';
      titleNode = document.createElement( 'strong' );
      titleNode.textContent = title;
      descriptionNode = document.createElement( 'span' );
      descriptionNode.className = 'labassistant-status-note';
      descriptionNode.textContent = description;
      head.appendChild( titleNode );
      head.appendChild( descriptionNode );
      section.appendChild( head );
      items.forEach( function ( item ) {
        itemNode = document.createElement( 'div' );
        itemNode.className = 'labassistant-form-fill-item';

        itemCopy = document.createElement( 'div' );
        itemCopy.className = 'labassistant-form-fill-copy';

        titleNode = document.createElement( 'strong' );
        titleNode.textContent = item.label || item;
        itemCopy.appendChild( titleNode );

        reasonNode = document.createElement( 'span' );
        reasonNode.className = 'labassistant-status-note';
        reasonNode.textContent = item.reason || description;
        itemCopy.appendChild( reasonNode );
        itemNode.appendChild( itemCopy );

        if ( item.evidence && item.evidence.length ) {
          chipList = document.createElement( 'div' );
          chipList.className = 'labassistant-form-missing-list';
          item.evidence.forEach( function ( evidenceItem ) {
            var chip = document.createElement( 'span' );
            chip.className = 'labassistant-form-missing-chip';
            chip.textContent = evidenceItem;
            chipList.appendChild( chip );
          } );
          itemNode.appendChild( chipList );
        }

        section.appendChild( itemNode );
      } );
      notice.appendChild( section );
    }

    if ( checklistSections ) {
      appendChecklistSection(
        '待确认字段',
        checklistSections.pendingText || '这些字段已有候选值，但仍需学生确认。',
        checklistSections.pendingItems || []
      );
      appendChecklistSection(
        '待补充字段',
        checklistSections.missingText || '这些字段当前还没有可直接回填的候选值。',
        checklistSections.missingItems || []
      );
      return;
    }

    chipList = document.createElement( 'div' );
    chipList.className = 'labassistant-form-missing-list';
    missingItems.forEach( function ( item ) {
      var chip = document.createElement( 'span' );
      chip.className = 'labassistant-form-missing-chip';
      chip.textContent = item.label || item;
      chipList.appendChild( chip );
    } );
    notice.appendChild( chipList );
  }

  function restoreSubmissionGuidance(config) {
    var title = config.defaultContextTitle || config.currentTitle || '';
    var key;
    var raw;
    var payload;
    if ( !title || !window.sessionStorage ) {
      return;
    }
    key = getSubmissionGuidanceStorageKey( title, window.location.host );
    raw = sessionStorage.getItem( key );
    if ( !raw ) {
      clearSubmitChecklistNotice();
      return;
    }
    try {
      payload = JSON.parse( raw );
    } catch ( error ) {
      sessionStorage.removeItem( key );
      clearSubmitChecklistNotice();
      return;
    }
    setSubmitChecklistNotice( config, payload );
  }

  function applyDraftHandoffToSourceEditor( config ) {
    var textarea = document.getElementById( 'wpTextbox1' );
    var editorUtils = getEditorUtils();
    var title = config.defaultContextTitle || config.currentTitle || '';
    var key;
    var raw;
    var payload;
    var helper;
    var notice;
    var nextContent = '';
    var targetSection = '';

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

    targetSection = String( payload.target_section || '' ).trim();
    nextContent = payload.content;
    if ( targetSection && editorUtils && editorUtils.replaceManagedPageSectionBody ) {
      try {
        nextContent = editorUtils.replaceManagedPageSectionBody(
          textarea.value,
          targetSection,
          ( payload.structured_payload && payload.structured_payload.内容 ) || payload.content
        );
      } catch ( error ) {
        console.warn( error );
        return;
      }
    }

    textarea.value = nextContent;
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
    notice.textContent = targetSection ?
      ( '已替换区块“' + targetSection + '”内容，页面尚未保存。' ) :
      '已从可视化编辑页带入草稿，页面尚未保存。';
    helper.appendChild( notice );
  }

  function uploadPastedImageToWiki( config, textarea, file ) {
    var uploadUtils = getEditorUploadUtils();
    var pageTitle = config.defaultContextTitle || config.currentTitle || 'clipboard-image';
    var filename;
    var api;

    if ( !uploadUtils || !uploadUtils.buildClipboardUploadFilename || !uploadUtils.buildWikiImageMarkup || !uploadUtils.insertTextAtCursor ) {
      return Promise.reject( new Error( '编辑器上传工具未加载' ) );
    }

    filename = uploadUtils.buildClipboardUploadFilename( pageTitle, file.type, new Date() );
    api = new mw.Api();

    setSourceEditorStatus( '正在上传粘贴图片到 Wiki…', 'pending' );

    return api.upload( file, {
      filename: filename,
      comment: 'Pasted from source editor via LabAssistant',
      ignorewarnings: true
    } ).then( function ( result ) {
      var actualName = result && result.upload && result.upload.filename ? result.upload.filename : filename;
      uploadUtils.insertTextAtCursor( textarea, uploadUtils.buildWikiImageMarkup( actualName ) );
      setSourceEditorStatus( '图片已上传到 Wiki，并插入文件语法。页面尚未保存。', 'success' );
      return result;
    } ).catch( function ( code, result ) {
      var detail = code;
      if ( result && result.error && result.error.info ) {
        detail = result.error.info;
      }
      setSourceEditorStatus( '图片上传失败：' + String( detail || '未知错误' ), 'error' );
      throw result || code;
    } );
  }

  function ensureSourceEditorImagePaste( config ) {
    var textarea = document.getElementById( 'wpTextbox1' );
    var attachmentUtils = getAttachmentUtils();
    var uploadUtils = getEditorUploadUtils();

    if ( !textarea || textarea.dataset.labassistantPasteUploadBound === 'true' ) {
      return;
    }

    textarea.dataset.labassistantPasteUploadBound = 'true';
    textarea.addEventListener( 'paste', function ( event ) {
      var pastedFiles;
      var imageFiles;
      if ( !attachmentUtils || !attachmentUtils.extractClipboardFiles || !uploadUtils || !uploadUtils.isSupportedWikiImageFile ) {
        return;
      }
      if ( !event.clipboardData || !event.clipboardData.items ) {
        return;
      }
      pastedFiles = attachmentUtils.extractClipboardFiles( event.clipboardData.items );
      imageFiles = pastedFiles.filter( uploadUtils.isSupportedWikiImageFile );
      if ( !imageFiles.length ) {
        return;
      }
      event.preventDefault();
      imageFiles.reduce( function ( chain, file ) {
        return chain.then( function () {
          return uploadPastedImageToWiki( config, textarea, file );
        } );
      }, Promise.resolve() ).catch( function ( error ) {
        console.warn( error );
      } );
    } );
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

    window.addEventListener( 'labassistant:submission-guidance', function ( event ) {
      setSubmitChecklistNotice( config, event.detail || {} );
    } );
    window.addEventListener( 'labassistant:open-pdf-reader', function ( event ) {
      var utils = getPdfReaderUtils();
      var detail = event && event.detail ? event.detail : {};
      var source = utils && utils.normalizePdfReaderSource ? utils.normalizePdfReaderSource( detail.source ) : null;
      if ( !source ) {
        return;
      }
      ensureFloatingPdfReader( config, source );
    } );

    if ( config.mountMode === 'special' ) {
      mountSpecialWorkspace( config );
      return;
    }

    ensureLauncherButton( config );
    ensureLiteratureGuidePdfReader( config );
    if ( editorMode === 'source_edit' ) {
      ensureEditorHelperButton( config );
      applyDraftHandoffToSourceEditor( config );
      ensureSourceEditorImagePaste( config );
      restoreSubmissionGuidance( config );
      return;
    }
    if ( editorMode === 'pageforms_edit' ) {
      ensurePageFormsHelperButton( config );
      restoreSubmissionGuidance( config );
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
