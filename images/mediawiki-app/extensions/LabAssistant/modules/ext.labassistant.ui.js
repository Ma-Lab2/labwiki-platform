( function () {
  var STORAGE_KEY = 'labassistant-active-session-id';
  var MODEL_STORAGE_KEY = 'labassistant-selected-model';
  var MODEL_FAMILY_STORAGE_KEY = 'labassistant-selected-model-family';
  var HOST_STORAGE_KEY = 'labassistant-active-host';
  var MODEL_PREF_VERSION_KEY = 'labassistant-model-pref-version';
  var MODEL_PREF_VERSION = '2026-03-20-drawer-chat-1';
  var DRAWER_ROOT_ID = 'labassistant-drawer-root';
  var DRAFT_HANDOFF_FALLBACK_PREFIX = 'labassistant-draft-handoff::';
  var SUBMISSION_GUIDANCE_FALLBACK_PREFIX = 'labassistant-submission-guidance::';

  function getEditorUtils() {
    return window.LabAssistantEditorUtils || ( window.mw && mw.labassistantEditorUtils ) || null;
  }

  function getShellUtils() {
    return window.LabAssistantShellUtils || ( window.mw && mw.labassistantShellUtils ) || null;
  }

  function getAttachmentUtils() {
    return window.LabAssistantAttachmentUtils || ( window.mw && mw.labassistantAttachmentUtils ) || null;
  }

  function getSessionExportUtils() {
    return window.LabAssistantSessionExportUtils || ( window.mw && mw.labassistantSessionExportUtils ) || null;
  }

  function getPdfIngestUtils() {
    return window.LabAssistantPdfIngestUtils || ( window.mw && mw.labassistantPdfIngestUtils ) || null;
  }

  function dispatchPdfReaderOpen( detail ) {
    if ( typeof window === 'undefined' || typeof window.CustomEvent !== 'function' ) {
      return;
    }
    window.dispatchEvent( new CustomEvent( 'labassistant:open-pdf-reader', {
      detail: detail || {}
    } ) );
  }

  function getDraftHandoffKey( title, host ) {
    var editorUtils = getEditorUtils();
    if ( editorUtils && editorUtils.buildDraftHandoffStorageKey ) {
      return editorUtils.buildDraftHandoffStorageKey( title, host );
    }
    return DRAFT_HANDOFF_FALLBACK_PREFIX + String( host || '' ) + '::' + String( title || '' );
  }

  function getSubmissionGuidanceKey( title, host ) {
    var editorUtils = getEditorUtils();
    if ( editorUtils && editorUtils.buildSubmissionGuidanceStorageKey ) {
      return editorUtils.buildSubmissionGuidanceStorageKey( title, host );
    }
    return SUBMISSION_GUIDANCE_FALLBACK_PREFIX + String( host || '' ) + '::' + String( title || '' );
  }

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
      } else if ( key === 'checked' ) {
        el.checked = !!value;
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

  function clearNode( node ) {
    while ( node.firstChild ) {
      node.removeChild( node.firstChild );
    }
  }

  function escapeHtml( value ) {
    return String( value || '' )
      .replace( /&/g, '&amp;' )
      .replace( /</g, '&lt;' )
      .replace( />/g, '&gt;' )
      .replace( /"/g, '&quot;' )
      .replace( /'/g, '&#39;' );
  }

  function escapeAttr( value ) {
    return escapeHtml( value );
  }

  function sanitizeUrl( value ) {
    if ( !value ) {
      return null;
    }
    var trimmed = String( value ).trim();
    if ( !trimmed ) {
      return null;
    }
    if ( trimmed.charAt( 0 ) === '#' || trimmed.charAt( 0 ) === '/' ) {
      return trimmed;
    }
    try {
      var parsed = new URL( trimmed, window.location.origin );
      var protocol = parsed.protocol.toLowerCase();
      if ( protocol === 'http:' || protocol === 'https:' ) {
        return parsed.toString();
      }
    } catch ( error ) {
      return null;
    }
    return null;
  }

  function getCanonicalHost() {
    if ( !window.mw || !mw.config ) {
      return null;
    }
    var canonicalServer = mw.config.get( 'wgServer' );
    if ( !canonicalServer ) {
      return null;
    }
    try {
      return new URL( canonicalServer, window.location.origin ).host;
    } catch ( error ) {
      return null;
    }
  }

  function getHostName( host ) {
    if ( !host ) {
      return '';
    }
    return String( host ).split( ':' )[ 0 ].toLowerCase();
  }

  function isLoopbackHost( host ) {
    var hostName = getHostName( host );
    return hostName === '127.0.0.1' || hostName === 'localhost';
  }

  function isEquivalentPrivateHost( left, right ) {
    if ( !left || !right ) {
      return left === right;
    }
    if ( left === right ) {
      return true;
    }
    return isLoopbackHost( left ) && isLoopbackHost( right ) ||
      isLoopbackHost( left ) && !isLoopbackHost( right ) ||
      !isLoopbackHost( left ) && isLoopbackHost( right );
  }

  function clearAssistantLocalState() {
    localStorage.removeItem( STORAGE_KEY );
    localStorage.removeItem( MODEL_STORAGE_KEY );
    localStorage.removeItem( MODEL_FAMILY_STORAGE_KEY );
  }

  function syncModelPreferenceVersion() {
    var storedVersion = localStorage.getItem( MODEL_PREF_VERSION_KEY );
    if ( storedVersion && storedVersion !== MODEL_PREF_VERSION ) {
      localStorage.removeItem( MODEL_STORAGE_KEY );
      localStorage.removeItem( MODEL_FAMILY_STORAGE_KEY );
    }
    localStorage.setItem( MODEL_PREF_VERSION_KEY, MODEL_PREF_VERSION );
  }

  function syncHostScopedState() {
    var currentHost = window.location.host;
    var storedHost = localStorage.getItem( HOST_STORAGE_KEY );
    var canonicalHost = getCanonicalHost();

    if ( storedHost && !isEquivalentPrivateHost( storedHost, currentHost ) ) {
      clearAssistantLocalState();
    }

    if ( canonicalHost && !isEquivalentPrivateHost( currentHost, canonicalHost ) ) {
      clearAssistantLocalState();
      localStorage.setItem( HOST_STORAGE_KEY, canonicalHost );
      window.location.replace(
        window.location.protocol + '//' + canonicalHost + window.location.pathname + window.location.search + window.location.hash
      );
      return false;
    }

    localStorage.setItem( HOST_STORAGE_KEY, currentHost );
    return true;
  }

  function normalizeSourceUrl( url ) {
    var safe = sanitizeUrl( url );
    if ( !safe ) {
      return null;
    }
    try {
      var parsed = new URL( safe, window.location.origin );
      if (
        parsed.hostname === 'host.docker.internal' ||
        parsed.hostname === '192.168.1.2' ||
        parsed.hostname === '127.0.0.1' ||
        parsed.hostname === 'localhost'
      ) {
        parsed.protocol = window.location.protocol;
        parsed.host = window.location.host;
      }
      return parsed.toString();
    } catch ( error ) {
      return safe;
    }
  }

  function renderInlineMarkdown( source ) {
    var placeholders = [];
    var text = String( source || '' );

    text = text.replace( /`([^`]+)`/g, function ( match, code ) {
      var replacement = '<code>' + escapeHtml( code ) + '</code>';
      var token = '\u0000' + placeholders.length + '\u0000';
      placeholders.push( replacement );
      return token;
    } );

    text = escapeHtml( text );

    text = text.replace( /\[([^\]]+)\]\(([^)]+)\)/g, function ( match, label, url ) {
      var safeUrl = sanitizeUrl( url );
      if ( !safeUrl ) {
        return label;
      }
      return '<a href="' + escapeAttr( safeUrl ) + '" target="_blank" rel="noopener">' + label + '</a>';
    } );

    text = text.replace( /\*\*([^*]+)\*\*/g, '<strong>$1</strong>' );
    text = text.replace( /\*([^*]+)\*/g, '<em>$1</em>' );

    text = text.replace( /\u0000(\d+)\u0000/g, function ( match, index ) {
      return placeholders[ Number( index ) ] || '';
    } );

    return text;
  }

  function splitPipeRow( line ) {
    var normalized = line.trim();
    if ( normalized.charAt( 0 ) === '|' ) {
      normalized = normalized.slice( 1 );
    }
    if ( normalized.charAt( normalized.length - 1 ) === '|' ) {
      normalized = normalized.slice( 0, -1 );
    }
    return normalized.split( '|' ).map( function ( cell ) {
      return cell.trim();
    } );
  }

  function isTableSeparator( line ) {
    return /^\s*\|?[\s:-]+(?:\|[\s:-]+)+\|?\s*$/.test( line || '' );
  }

  function renderMarkdownFallback( source ) {
    var lines = String( source || '' ).replace( /\r\n?/g, '\n' ).split( '\n' );
    var html = [];
    var index = 0;

    function flushParagraph( buffer ) {
      if ( !buffer.length ) {
        return;
      }
      html.push( '<p>' + renderInlineMarkdown( buffer.join( ' ' ).trim() ) + '</p>' );
      buffer.length = 0;
    }

    while ( index < lines.length ) {
      var line = lines[ index ];

      if ( !line.trim() ) {
        index += 1;
        continue;
      }

      if ( /^```/.test( line ) ) {
        var language = line.replace( /^```/, '' ).trim();
        var code = [];
        index += 1;
        while ( index < lines.length && !/^```/.test( lines[ index ] ) ) {
          code.push( lines[ index ] );
          index += 1;
        }
        if ( index < lines.length && /^```/.test( lines[ index ] ) ) {
          index += 1;
        }
        html.push(
          '<pre><code' +
          ( language ? ' class="language-' + escapeAttr( language ) + '"' : '' ) +
          '>' + escapeHtml( code.join( '\n' ) ) + '</code></pre>'
        );
        continue;
      }

      if ( /^#{1,6}\s+/.test( line ) ) {
        var depth = line.match( /^#+/ )[ 0 ].length;
        var headingText = line.replace( /^#{1,6}\s+/, '' ).trim();
        html.push( '<h' + depth + '>' + renderInlineMarkdown( headingText ) + '</h' + depth + '>' );
        index += 1;
        continue;
      }

      if ( line.indexOf( '|' ) !== -1 && index + 1 < lines.length && isTableSeparator( lines[ index + 1 ] ) ) {
        var headerCells = splitPipeRow( line );
        var bodyRows = [];
        index += 2;
        while ( index < lines.length && lines[ index ].indexOf( '|' ) !== -1 && lines[ index ].trim() ) {
          bodyRows.push( splitPipeRow( lines[ index ] ) );
          index += 1;
        }
        html.push( '<table><thead><tr>' + headerCells.map( function ( cell ) {
          return '<th>' + renderInlineMarkdown( cell ) + '</th>';
        } ).join( '' ) + '</tr></thead><tbody>' + bodyRows.map( function ( row ) {
          return '<tr>' + row.map( function ( cell ) {
            return '<td>' + renderInlineMarkdown( cell ) + '</td>';
          } ).join( '' ) + '</tr>';
        } ).join( '' ) + '</tbody></table>' );
        continue;
      }

      if ( /^>\s?/.test( line ) ) {
        var quote = [];
        while ( index < lines.length && /^>\s?/.test( lines[ index ] ) ) {
          quote.push( lines[ index ].replace( /^>\s?/, '' ) );
          index += 1;
        }
        html.push( '<blockquote>' + renderMarkdownFallback( quote.join( '\n' ) ) + '</blockquote>' );
        continue;
      }

      if ( /^\s*[-*]\s+/.test( line ) ) {
        var unordered = [];
        while ( index < lines.length && /^\s*[-*]\s+/.test( lines[ index ] ) ) {
          unordered.push( lines[ index ].replace( /^\s*[-*]\s+/, '' ) );
          index += 1;
        }
        html.push( '<ul>' + unordered.map( function ( item ) {
          return '<li>' + renderInlineMarkdown( item ) + '</li>';
        } ).join( '' ) + '</ul>' );
        continue;
      }

      if ( /^\s*\d+\.\s+/.test( line ) ) {
        var ordered = [];
        while ( index < lines.length && /^\s*\d+\.\s+/.test( lines[ index ] ) ) {
          ordered.push( lines[ index ].replace( /^\s*\d+\.\s+/, '' ) );
          index += 1;
        }
        html.push( '<ol>' + ordered.map( function ( item ) {
          return '<li>' + renderInlineMarkdown( item ) + '</li>';
        } ).join( '' ) + '</ol>' );
        continue;
      }

      var paragraph = [];
      while (
        index < lines.length &&
        lines[ index ].trim() &&
        !/^```/.test( lines[ index ] ) &&
        !/^#{1,6}\s+/.test( lines[ index ] ) &&
        !/^>\s?/.test( lines[ index ] ) &&
        !/^\s*[-*]\s+/.test( lines[ index ] ) &&
        !/^\s*\d+\.\s+/.test( lines[ index ] ) &&
        !( lines[ index ].indexOf( '|' ) !== -1 && index + 1 < lines.length && isTableSeparator( lines[ index + 1 ] ) )
      ) {
        paragraph.push( lines[ index ] );
        index += 1;
      }
      flushParagraph( paragraph );
    }

    return html.join( '' ) || '<p></p>';
  }

  function sanitizeRenderedMarkdown( html ) {
    var safeHtml = String( html || '' );
    var container;

    if ( !( window.DOMPurify && typeof window.DOMPurify.sanitize === 'function' ) ) {
      return null;
    }

    safeHtml = window.DOMPurify.sanitize( safeHtml, {
      USE_PROFILES: { html: true }
    } );

    container = document.createElement( 'div' );
    container.innerHTML = safeHtml;

    Array.from( container.querySelectorAll( 'a[href]' ) ).forEach( function ( anchor ) {
      var normalized = normalizeSourceUrl( anchor.getAttribute( 'href' ) );
      if ( normalized ) {
        anchor.setAttribute( 'href', normalized );
        anchor.setAttribute( 'target', '_blank' );
        anchor.setAttribute( 'rel', 'noopener' );
      } else {
        anchor.removeAttribute( 'href' );
      }
    } );

    return container.innerHTML || '<p></p>';
  }

  function renderMarkdown( source ) {
    var markdown = String( source || '' );

    if ( window.marked && typeof window.marked.parse === 'function' ) {
      try {
        var sanitizedHtml = sanitizeRenderedMarkdown( window.marked.parse( markdown, {
          breaks: true,
          gfm: true,
          headerIds: false,
          mangle: false
        } ) );
        if ( sanitizedHtml ) {
          return sanitizedHtml;
        }
      } catch ( error ) {
        console.warn( 'LabAssistant markdown renderer fell back to lightweight parser.', error );
      }
    }

    return renderMarkdownFallback( markdown );
  }

  function normalizeCodeLanguage( value ) {
    var normalized = String( value || '' )
      .trim()
      .toLowerCase()
      .replace( /^language-/, '' )
      .replace( /^lang-/, '' );
    var aliases = {
      js: 'javascript',
      ts: 'typescript',
      py: 'python',
      sh: 'bash',
      shell: 'bash',
      zsh: 'bash',
      console: 'bash',
      yml: 'yaml',
      md: 'markdown',
      plaintext: 'text',
      text: 'text'
    };
    return aliases[ normalized ] || normalized;
  }

  function formatCodeLanguageLabel( value ) {
    var normalized = normalizeCodeLanguage( value );
    var labels = {
      bash: 'Bash',
      javascript: 'JavaScript',
      json: 'JSON',
      markdown: 'Markdown',
      php: 'PHP',
      python: 'Python',
      sql: 'SQL',
      text: '文本',
      typescript: 'TypeScript',
      yaml: 'YAML'
    };
    return labels[ normalized ] || ( normalized ? normalized.toUpperCase() : '文本' );
  }

  function detectCodeLanguage( code ) {
    var classList = Array.from( code.classList || [] );
    var languageClass = classList.find( function ( className ) {
      return className.indexOf( 'language-' ) === 0 || className.indexOf( 'lang-' ) === 0;
    } );
    return normalizeCodeLanguage( languageClass || '' );
  }

  function getHighlightClient() {
    if ( window.hljs ) {
      return window.hljs;
    }
    if ( typeof hljs !== 'undefined' ) {
      return hljs;
    }
    return null;
  }

  function enhanceMarkdownContainers( container ) {
    Array.from( container.querySelectorAll( '.labassistant-markdown' ) ).forEach( function ( markdownNode ) {
      Array.from( markdownNode.querySelectorAll( 'pre > code' ) ).forEach( function ( code ) {
        var pre = code.parentNode;
        var providedLanguage = detectCodeLanguage( code );
        var rawText = code.textContent || '';
        var displayLanguage = providedLanguage || 'text';
        var highlightClient = getHighlightClient();

        if ( highlightClient && typeof highlightClient.highlightElement === 'function' ) {
          try {
            if ( providedLanguage && typeof highlightClient.getLanguage === 'function' && highlightClient.getLanguage( providedLanguage ) ) {
              code.classList.add( 'language-' + providedLanguage );
              highlightClient.highlightElement( code );
              displayLanguage = providedLanguage;
            } else if ( rawText.trim() && typeof highlightClient.highlightAuto === 'function' ) {
              var autoResult = highlightClient.highlightAuto( rawText );
              code.innerHTML = autoResult.value;
              code.classList.add( 'hljs' );
              displayLanguage = normalizeCodeLanguage( autoResult.language ) || 'text';
            }
          } catch ( error ) {
            console.warn( 'LabAssistant code highlighting fell back to plain text.', error );
          }
        }

        var wrapper = createEl( 'div', { className: 'labassistant-code-block' } );
        var header = createEl( 'div', { className: 'labassistant-code-header' } );
        var languageBadge = createEl( 'span', {
          className: 'labassistant-code-language',
          text: formatCodeLanguageLabel( displayLanguage )
        } );
        var copyButton = createEl( 'button', {
          type: 'button',
          className: 'labassistant-code-copy',
          text: '复制'
        } );

        copyButton.addEventListener( 'click', function () {
          var resetLabel = function () {
            window.setTimeout( function () {
              copyButton.textContent = '复制';
            }, 1200 );
          };
          if ( navigator.clipboard && typeof navigator.clipboard.writeText === 'function' ) {
            navigator.clipboard.writeText( rawText ).then( function () {
              copyButton.textContent = '已复制';
              resetLabel();
            } ).catch( function () {
              copyButton.textContent = '复制失败';
              resetLabel();
            } );
            return;
          }
          copyButton.textContent = '请手动复制';
          resetLabel();
        } );

        header.appendChild( languageBadge );
        header.appendChild( copyButton );
        pre.parentNode.insertBefore( wrapper, pre );
        wrapper.appendChild( header );
        wrapper.appendChild( pre );
      } );
    } );
  }

  function shortSessionId( value ) {
    if ( !value ) {
      return '新会话';
    }
    return value.slice( 0, 8 );
  }

  function turnToResult( turn ) {
    if ( !turn ) {
      return null;
    }
    return {
      session_id: turn.session_id || null,
      turn_id: turn.turn_id || null,
      task_type: turn.task_type,
      answer: turn.answer || '',
      step_stream: turn.step_stream || [],
      sources: turn.sources || [],
      confidence: turn.confidence,
      unresolved_gaps: turn.unresolved_gaps || [],
      suggested_followups: turn.suggested_followups || [],
      action_trace: turn.action_trace || [],
      draft_preview: turn.draft_preview || null,
      draft_commit_result: turn.draft_commit_result || null,
      write_preview: turn.write_preview || null,
      write_result: turn.write_result || null,
      result_fill: turn.result_fill || null,
      pdf_ingest_review: turn.pdf_ingest_review || null,
      pdf_control_preview: turn.pdf_control_preview || null,
      pdf_control_commit_result: turn.pdf_control_commit_result || null,
      model_info: turn.model_info || null,
      form_fill_notice: turn.form_fill_notice || '',
      editor_fill_notice: turn.editor_fill_notice || ''
    };
  }

  function upsertStep( steps, step ) {
    var next = ( steps || [] ).slice();
    var index = next.findIndex( function ( item ) {
      return item.stage === step.stage;
    } );
    if ( index >= 0 ) {
      next[ index ] = step;
    } else {
      next.push( step );
    }
    return next;
  }

  function parseEventBlock( block ) {
    var lines = block.split( /\r?\n/ );
    var eventName = 'message';
    var dataLines = [];
    lines.forEach( function ( line ) {
      if ( line.indexOf( 'event:' ) === 0 ) {
        eventName = line.slice( 6 ).trim();
      } else if ( line.indexOf( 'data:' ) === 0 ) {
        dataLines.push( line.slice( 5 ).trim() );
      }
    } );
    if ( !dataLines.length ) {
      return null;
    }
    try {
      return {
        event: eventName,
        data: JSON.parse( dataLines.join( '\n' ) )
      };
    } catch ( error ) {
      return {
        event: 'error',
        data: { detail: '无法解析 SSE 数据。' }
      };
    }
  }

  function streamChat( apiBase, payload, onEvent ) {
    return fetch( apiBase + '/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify( payload )
    } ).then( function ( response ) {
      if ( !response.ok || !response.body ) {
        return response.text().then( function ( body ) {
          throw new Error( body || '流式请求失败' );
        } );
      }
      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = '';

      function pump() {
        return reader.read().then( function ( result ) {
          if ( result.done ) {
            if ( buffer.trim() ) {
              var finalEvent = parseEventBlock( buffer.trim() );
              if ( finalEvent ) {
                onEvent( finalEvent );
              }
            }
            return;
          }
          buffer += decoder.decode( result.value, { stream: true } );
          var parts = buffer.split( /\n\n/ );
          buffer = parts.pop() || '';
          parts.forEach( function ( part ) {
            var parsed = parseEventBlock( part.trim() );
            if ( parsed ) {
              onEvent( parsed );
            }
          } );
          return pump();
        } );
      }

      return pump();
    } );
  }

  function loadSession( apiBase, sessionId ) {
    return fetch( apiBase + '/session/' + encodeURIComponent( sessionId ), {
      credentials: 'same-origin'
    } ).then( function ( response ) {
      return response.json().then( function ( body ) {
        if ( !response.ok ) {
          throw new Error( body.detail || '会话读取失败' );
        }
        return body;
      } );
    } );
  }

  function loadSessionHistory( apiBase, userName ) {
    var url = apiBase + '/sessions';
    if ( userName ) {
      url += '?user_name=' + encodeURIComponent( userName );
    }
    return fetch( url, {
      credentials: 'same-origin'
    } ).then( function ( response ) {
      return response.json().then( function ( body ) {
        if ( !response.ok ) {
          throw new Error( body.detail || '历史会话读取失败' );
        }
        return body;
      } );
    } );
  }

  function loadModelCatalog( apiBase, includeAll ) {
    var suffix = includeAll ? '?include_all=true' : '';
    return fetch( apiBase + '/models/catalog' + suffix, {
      credentials: 'same-origin'
    } ).then( function ( response ) {
      return response.json().then( function ( body ) {
        if ( !response.ok ) {
          throw new Error( body.detail || '模型目录读取失败' );
        }
        return body;
      } );
    } );
  }

  function updateSessionModel( apiBase, sessionId, payload ) {
    return fetch( apiBase + '/session/' + encodeURIComponent( sessionId ) + '/model', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify( payload )
    } ).then( function ( response ) {
      return response.json().then( function ( body ) {
        if ( !response.ok ) {
          throw new Error( body.detail || '模型切换失败' );
        }
        return body;
      } );
    } );
  }

  function parseDownloadFilename( headerValue ) {
    var match;
    if ( !headerValue ) {
      return '';
    }
    match = /filename\*=UTF-8''([^;]+)/i.exec( headerValue );
    if ( match && match[ 1 ] ) {
      try {
        return decodeURIComponent( match[ 1 ] );
      } catch ( error ) {
        return match[ 1 ];
      }
    }
    match = /filename="?([^\";]+)"?/i.exec( headerValue );
    return match && match[ 1 ] ? match[ 1 ] : '';
  }

  function downloadSessionMarkdown( apiBase, sessionItem, userName ) {
    var exportUtils = getSessionExportUtils();
    var url = apiBase + '/session/' + encodeURIComponent( sessionItem.session_id ) + '/export.md';
    if ( userName ) {
      url += '?user_name=' + encodeURIComponent( userName );
    }
    return fetch( url, {
      credentials: 'same-origin'
    } ).then( function ( response ) {
      if ( !response.ok ) {
        return response.text().then( function ( body ) {
          try {
            var parsed = JSON.parse( body || '{}' );
            throw new Error( parsed.detail || 'Markdown 导出失败' );
          } catch ( error ) {
            if ( error && error.message && error.message !== 'Unexpected end of JSON input' ) {
              throw error;
            }
            throw new Error( body || 'Markdown 导出失败' );
          }
        } );
      }
      return response.blob().then( function ( blob ) {
        var filename = parseDownloadFilename( response.headers.get( 'content-disposition' ) ) ||
          ( exportUtils && exportUtils.buildSessionExportFileName ?
            exportUtils.buildSessionExportFileName( sessionItem ) :
            'labassistant-session.md' );
        var objectUrl = URL.createObjectURL( blob );
        var anchor = createEl( 'a', {
          href: objectUrl,
          download: filename
        } );
        document.body.appendChild( anchor );
        anchor.click();
        anchor.remove();
        setTimeout( function () {
          URL.revokeObjectURL( objectUrl );
        }, 0 );
        return filename;
      } );
    } );
  }

  function requestPdfDraftPreview( apiBase, payload ) {
    return fetch( apiBase + '/pdf/draft/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify( payload )
    } ).then( function ( response ) {
      return response.json().then( function ( body ) {
        if ( !response.ok ) {
          throw new Error( body.detail || 'PDF 草稿预览生成失败' );
        }
        return body;
      } );
    } );
  }

  function requestPdfControlPreview( apiBase, payload ) {
    return fetch( apiBase + '/pdf/control/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify( payload )
    } ).then( function ( response ) {
      return response.json().then( function ( body ) {
        if ( !response.ok ) {
          throw new Error( body.detail || 'Control 正式写入预览生成失败' );
        }
        var ingestUtils = getPdfIngestUtils();
        return ingestUtils && ingestUtils.normalizePdfControlPreview ?
          ingestUtils.normalizePdfControlPreview( body ) :
          body;
      } );
    } );
  }

  function commitPdfControlPreview( apiBase, previewId ) {
    return fetch( apiBase + '/pdf/control/commit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify( {
        preview_id: previewId
      } )
    } ).then( function ( response ) {
      return response.json().then( function ( body ) {
        if ( !response.ok ) {
          throw new Error( body.detail || 'Control 正式写入失败' );
        }
        return body;
      } );
    } );
  }

  function uploadAttachment( apiBase, file ) {
    var formData = new FormData();
    formData.append( 'file', file );
    return fetch( apiBase + '/attachments', {
      method: 'POST',
      body: formData,
      credentials: 'same-origin'
    } ).then( function ( response ) {
      return response.json().then( function ( body ) {
        if ( !response.ok ) {
          throw new Error( body.detail || '附件上传失败' );
        }
        return body;
      } );
    } );
  }

  function deleteAttachment( apiBase, attachmentId ) {
    return fetch( apiBase + '/attachments/' + encodeURIComponent( attachmentId ), {
      method: 'DELETE',
      credentials: 'same-origin'
    } ).then( function ( response ) {
      return response.json().then( function ( body ) {
        if ( !response.ok ) {
          throw new Error( body.detail || '附件删除失败' );
        }
        return body;
      } );
    } );
  }

  function getControlType( control ) {
    if ( !control ) {
      return 'text';
    }
    if ( control.tagName === 'TEXTAREA' ) {
      return 'textarea';
    }
    if ( control.tagName === 'SELECT' ) {
      return control.multiple ? 'multiselect' : 'select';
    }
    if ( control.getAttribute( 'role' ) === 'searchbox' ) {
      return 'tokens';
    }
    return 'text';
  }

  function findPageFormRoot() {
    return document.querySelector( '#pfForm, form[action*="Special:FormEdit"], form[action*="action=formedit"]' );
  }

  function extractPageFormFieldLabel( control ) {
    var label = '';
    var probe = control.closest( 'dd, li, div, td, p' );

    if ( control.labels && control.labels.length ) {
      label = control.labels[ 0 ].textContent || '';
    }
    while ( !label && probe ) {
      probe = probe.previousElementSibling;
      if ( !probe ) {
        break;
      }
      if ( /^(DT|LABEL|TH)$/.test( probe.tagName ) ) {
        label = probe.textContent || '';
        break;
      }
    }
    if ( !label ) {
      label = control.getAttribute( 'aria-label' ) || control.getAttribute( 'placeholder' ) || control.name || control.id || '';
    }
    if ( control.name && control.name.indexOf( '[' ) !== -1 ) {
      label = control.name.replace( /^[^\[]+\[/, '' ).replace( /\](?:\[\])?$/, '' );
    }
    label = label.replace( /^搜索/, '' ).replace( /\s+/g, ' ' ).trim();
    return label;
  }

  function collectPageFormFields() {
    var root = findPageFormRoot();
    var seen = {};
    if ( !root ) {
      return [];
    }
    return Array.from( root.querySelectorAll( 'input, textarea, select' ) ).map( function ( control ) {
      var type = ( control.type || '' ).toLowerCase();
      var key;
      var label;
      var controlType;
      if ( type === 'hidden' || type === 'submit' || type === 'button' || type === 'checkbox' || type === 'radio' ) {
        return null;
      }
      key = control.name || control.id;
      label = extractPageFormFieldLabel( control );
      controlType = getControlType( control );
      if ( !key || !label ) {
        return null;
      }
      if ( seen[ key ] ) {
        return null;
      }
      seen[ key ] = true;
      return {
        key: key,
        label: label,
        controlType: controlType,
        element: control
      };
    } ).filter( Boolean );
  }

  function dispatchTextEntry( element, value ) {
    element.focus();
    element.value = value;
    element.dispatchEvent( new Event( 'input', { bubbles: true } ) );
    element.dispatchEvent( new Event( 'change', { bubbles: true } ) );
  }

  function dispatchMultiSelectEntry( element, values ) {
    var normalizedValues;
    var selectedValues;

    if ( !element || element.tagName !== 'SELECT' || !element.multiple ) {
      return false;
    }

    normalizedValues = ( Array.isArray( values ) ? values : [] )
      .map( function ( value ) {
        return String( value || '' ).trim();
      } )
      .filter( Boolean );
    selectedValues = [];

    Array.from( element.options || [] ).forEach( function ( option ) {
      option.selected = false;
    } );

    normalizedValues.forEach( function ( value ) {
      var option = Array.from( element.options || [] ).find( function ( candidate ) {
        return String( candidate.value || '' ).trim() === value ||
          String( candidate.text || '' ).trim() === value;
      } );
      if ( !option ) {
        option = new Option( value, value, true, true );
        element.appendChild( option );
      }
      option.selected = true;
      selectedValues.push( option.value );
    } );

    element.value = selectedValues.length ? selectedValues[ 0 ] : '';
    element.dispatchEvent( new Event( 'input', { bubbles: true } ) );
    element.dispatchEvent( new Event( 'change', { bubbles: true } ) );
    if ( window.jQuery ) {
      window.jQuery( element ).trigger( 'change' );
    }
    return true;
  }

  function dispatchTokenEntry( element, values ) {
    if ( dispatchMultiSelectEntry( element, values ) ) {
      return true;
    }
    return values.every( function ( value ) {
      element.focus();
      element.value = value;
      element.dispatchEvent( new Event( 'input', { bubbles: true } ) );
      element.dispatchEvent( new KeyboardEvent( 'keydown', { bubbles: true, key: 'Enter' } ) );
      element.dispatchEvent( new KeyboardEvent( 'keypress', { bubbles: true, key: 'Enter' } ) );
      element.dispatchEvent( new KeyboardEvent( 'keyup', { bubbles: true, key: 'Enter' } ) );
      return true;
    } );
  }

  function applyPageFormMatch(match) {
    var element = match && match.field && match.field.element;
    if ( !element ) {
      return false;
    }
    if ( match.controlType === 'tokens' || match.controlType === 'multiselect' ) {
      return dispatchTokenEntry( element, Array.isArray( match.value ) ? match.value : [ String( match.value || '' ) ] );
    }
    if ( match.controlType === 'select' ) {
      element.value = String( match.value || '' );
      element.dispatchEvent( new Event( 'input', { bubbles: true } ) );
      element.dispatchEvent( new Event( 'change', { bubbles: true } ) );
      return true;
    }
    dispatchTextEntry( element, String( match.value || '' ) );
    return true;
  }

  function buildFormSuggestionMap(result) {
    var editorUtils = getEditorUtils();
    if ( result.result_fill && result.result_fill.field_suggestions ) {
      return result.result_fill.field_suggestions;
    }
    if ( result.write_preview && result.write_preview.structured_fields ) {
      return result.write_preview.structured_fields;
    }
    if ( result.draft_preview && result.draft_preview.structured_fields ) {
      return result.draft_preview.structured_fields;
    }
    if ( editorUtils && editorUtils.parseStructuredFieldSuggestions ) {
      return editorUtils.parseStructuredFieldSuggestions(
        result.answer ||
        ( result.write_preview && result.write_preview.preview_text ) ||
        ( result.draft_preview && result.draft_preview.content ) ||
        ''
      );
    }
    return {};
  }

  function buildFormMissingFields(result) {
    return buildFormMissingDetails( result ).map( function ( entry ) {
      return entry.label;
    } );
  }

  function buildFormMissingDetails(result) {
    var editorUtils = getEditorUtils();
    if ( result.result_fill && Array.isArray( result.result_fill.missing_items ) ) {
      if ( editorUtils && editorUtils.normalizeMissingItemEntries ) {
        return editorUtils.normalizeMissingItemEntries( result.result_fill.missing_items );
      }
      if ( editorUtils && editorUtils.normalizeFieldLabels ) {
        return editorUtils.normalizeFieldLabels( result.result_fill.missing_items ).map( function ( label ) {
          return { label: label, reason: '', evidence: [] };
        } );
      }
      return result.result_fill.missing_items.map( function ( label ) {
        return { label: label, reason: '', evidence: [] };
      } );
    }
    if ( editorUtils && editorUtils.parseMissingFields ) {
      var parsedMissingFields = editorUtils.parseMissingFields(
        result.answer ||
        ( result.write_preview && result.write_preview.preview_text ) ||
        ( result.draft_preview && result.draft_preview.content ) ||
        ''
      );
      if ( editorUtils.normalizeMissingItemEntries ) {
        return editorUtils.normalizeMissingItemEntries( parsedMissingFields );
      }
      if ( editorUtils.normalizeFieldLabels ) {
        return editorUtils.normalizeFieldLabels( parsedMissingFields ).map( function ( label ) {
          return { label: label, reason: '', evidence: [] };
        } );
      }
      return parsedMissingFields.map( function ( label ) {
        return { label: label, reason: '', evidence: [] };
      } );
    }
    return [];
  }

  function extractEmbeddedShotTitle( value ) {
    var match = String( value || '' ).match( /(Shot:[^/]+)$/i );
    return match ? match[ 1 ] : '';
  }

  function extractEmbeddedFormName( value ) {
    var editorUtils = getEditorUtils();
    if ( editorUtils && editorUtils.extractFormNameFromTitle ) {
      return editorUtils.extractFormNameFromTitle( value );
    }
    var match = String( value || '' ).match( /编辑表格\/([^/]+)/ );
    return match ? match[ 1 ] : '';
  }

  function resolveEffectiveContextTitle( rawContextTitle, config ) {
    var explicit = String( rawContextTitle || '' ).trim();
    var defaultTitle = String( ( config && config.defaultContextTitle ) || '' ).trim();
    var currentTitle = String( ( config && config.currentTitle ) || '' ).trim();
    if ( explicit ) {
      return explicit;
    }
    if ( defaultTitle ) {
      return defaultTitle;
    }
    if ( /^Shot:/i.test( currentTitle ) ) {
      return currentTitle;
    }
    return extractEmbeddedShotTitle( currentTitle ) || currentTitle;
  }

  function inferWorkflowHint( question, contextTitle, attachments ) {
    var title = String( contextTitle || '' );
    var hasImage = ( attachments || [] ).some( function ( item ) {
      return item.kind === 'image' || String( item.mime_type || '' ).indexOf( 'image/' ) === 0;
    } );
    if ( !/^Shot:/i.test( title ) || !hasImage ) {
      return null;
    }
    return 'shot_result_fill';
  }

  function buildDraftHandoffPayload(config, result, content) {
    return {
      title: config.defaultContextTitle || config.currentTitle || '',
      source_mode: config.editorMode || 'default',
      content_type: result.draft_preview ? 'draft_preview' : 'answer',
      content: content,
      created_at: new Date().toISOString()
    };
  }

  function navigateToSourceEdit(config, content, result) {
    var payload = buildDraftHandoffPayload( config, result, content );
    var title = config.defaultContextTitle || config.currentTitle || '';
    var key = getDraftHandoffKey( title, window.location.host );
    sessionStorage.setItem( key, JSON.stringify( payload ) );
    var targetUrl = new URL( mw.util.getUrl( title ), window.location.origin );
    targetUrl.searchParams.set( 'action', 'edit' );
    window.location.assign( targetUrl.toString() );
  }

  function consumeDraftHandoff(title) {
    var key = getDraftHandoffKey( title, window.location.host );
    var raw = sessionStorage.getItem( key );
    if ( !raw ) {
      return null;
    }
    sessionStorage.removeItem( key );
    try {
      return JSON.parse( raw );
    } catch ( error ) {
      return null;
    }
  }

  function createWorkspace( config, options ) {
    var attachmentUtils = getAttachmentUtils();
    var apiBase = attachmentUtils && attachmentUtils.resolveApiBase ?
      attachmentUtils.resolveApiBase( config.apiBase || '/tools/assistant/api', window.location ) :
      ( config.apiBase || '/tools/assistant/api' );
    var variant = options.variant || 'plugin';
    var shellUtils = getShellUtils();
    var compactWorkspace = shellUtils && shellUtils.isCompactWorkspaceVariant ?
      shellUtils.isCompactWorkspaceVariant( variant ) :
      ( variant === 'drawer' || variant === 'plugin' || variant === 'mobile-sheet' );
    var editorUtils = getEditorUtils();
    var editorMode = editorUtils && editorUtils.detectEditorMode ? editorUtils.detectEditorMode( config ) : ( config.editorMode || 'default' );
    if ( editorMode === 'default' && findPageFormRoot() ) {
      editorMode = 'pageforms_edit';
    }
    var resolvedFormName = ( config.formContext && config.formContext.formName ) || extractEmbeddedFormName( config.currentTitle ) || '';
    var editorTextarea = document.getElementById( 'wpTextbox1' );
    var pageFormFields = editorMode === 'pageforms_edit' ? collectPageFormFields() : [];
    var consumedDraftHandoff = editorMode === 'source_edit' ? consumeDraftHandoff( config.defaultContextTitle || config.currentTitle || '' ) : null;
    var state = {
      sessionId: localStorage.getItem( STORAGE_KEY ) || null,
      selectedModel: localStorage.getItem( MODEL_STORAGE_KEY ) || null,
      selectedFamily: localStorage.getItem( MODEL_FAMILY_STORAGE_KEY ) || null,
      showAllModels: false,
      modelCatalog: null,
      turns: [],
      attachments: [],
      pendingQuestion: '',
      currentResult: null,
      showSettings: false,
      historyOpen: false,
      historySessions: [],
      historyLoaded: false,
      historyLoading: false,
      historyQuery: '',
      historyError: '',
      historyNotice: '',
      historyExportingSessionId: '',
      drawerPopoverOpen: false,
      uploadMenuOpen: false,
      renderTimer: null,
      sourceEditNotice: consumedDraftHandoff ? '已从上一页带入待填草稿，页面尚未保存。' : ''
    };

    function getPageFormRuntimeContext() {
      if ( editorUtils && editorUtils.resolvePageFormRuntimeContext ) {
        var runtimeContext = editorUtils.resolvePageFormRuntimeContext( {
          editorMode: editorMode,
          resolvedFormName: resolvedFormName,
          pageFormFields: pageFormFields,
          currentTitle: config.currentTitle,
          formContext: config.formContext,
          hasPageFormRoot: !!findPageFormRoot(),
          collectPageFormFields: collectPageFormFields
        } );
        editorMode = runtimeContext.editorMode;
        resolvedFormName = runtimeContext.resolvedFormName;
        pageFormFields = runtimeContext.pageFormFields;
      }

      return {
        editorMode: editorMode,
        resolvedFormName: resolvedFormName,
        pageFormFields: pageFormFields
      };
    }

    var root = createEl( 'div', {
      className: 'labassistant-workspace is-' + variant
    } );
    var transcript = createEl( 'div', {
      className: 'labassistant-transcript',
      'aria-live': 'polite'
    } );
    var sessionBadge = createEl( 'span', { className: 'labassistant-pill', text: '会话：新会话' } );
    var contextBadge = compactWorkspace ? null : createEl( 'span', {
      className: 'labassistant-pill labassistant-pill-soft',
      text: '上下文：未绑定页面'
    } );
    var contextSummary = createEl( 'div', {
      className: 'labassistant-context-display',
      text: '自动跟随当前页面'
    } );
    var composerContextHint = createEl( 'div', {
      className: 'labassistant-context-hint',
      text: '当前页：自动识别'
    } );
    var attachmentRow = createEl( 'div', {
      className: 'labassistant-attachment-row'
    } );
    var modelBadge = createEl( 'span', { className: 'labassistant-pill labassistant-pill-soft', text: '模型：载入中' } );

    var modeSelect = createEl( 'select' );
    var detailSelect = createEl( 'select' );
    var contextInput = createEl( 'input', {
      type: 'text',
      placeholder: '可选：Theory:RPA / Shot:2026-03-14-Run01-Shot001',
      value: config.defaultContextTitle || extractEmbeddedShotTitle( config.currentTitle ) || ''
    } );
    var familySelect = createEl( 'select' );
    var modelSelect = createEl( 'select' );
    var compactModelSelect = createEl( 'select', {
      className: 'labassistant-compact-model-select',
      'aria-label': '切换模型'
    } );
    var showAllToggle = createEl( 'input', { type: 'checkbox' } );
    var questionInput = createEl( 'textarea', {
      className: 'labassistant-question-input',
      placeholder: '例如：把当前页整理成词条草案；把这页整理成周实验日志条目。',
      rows: '3',
      'aria-label': '输入问题'
    } );
    var imageUploadInput = createEl( 'input', {
      type: 'file',
      accept: 'image/png,image/jpeg,image/webp',
      hidden: 'hidden'
    } );
    var documentUploadInput = createEl( 'input', {
      type: 'file',
      accept: '.pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown',
      hidden: 'hidden'
    } );
    var plusButton = createEl( 'button', {
      type: 'button',
      className: 'labassistant-plus-button',
      text: '+',
      'aria-label': '添加附件'
    } );
    var uploadImageButton = createEl( 'button', {
      type: 'button',
      className: 'labassistant-upload-action',
      text: '上传图片'
    } );
    var uploadDocumentButton = createEl( 'button', {
      type: 'button',
      className: 'labassistant-upload-action',
      text: '上传文档'
    } );
    var uploadMenu = createEl( 'div', {
      className: 'labassistant-upload-menu',
      hidden: 'hidden'
    }, [
      uploadImageButton,
      uploadDocumentButton
    ] );
    var sendButton = createEl( 'button', {
      type: 'button',
      className: 'labassistant-send-button',
      text: '发送'
    } );
    var historyButton = createEl( 'button', {
      type: 'button',
      className: 'labassistant-toolbar-button',
      text: '历史'
    } );
    var resetButton = createEl( 'button', {
      type: 'button',
      className: 'labassistant-toolbar-button',
      text: '新会话'
    } );
    var settingsButton = createEl( 'button', {
      type: 'button',
      className: 'labassistant-toolbar-button',
      text: '选项'
    } );
    var closeButton = options.onClose ? createEl( 'button', {
      type: 'button',
      className: 'labassistant-toolbar-button',
      text: options.closeLabel || '收起'
    } ) : null;

    if ( config.seedQuestion ) {
      questionInput.value = config.seedQuestion;
    }

    ( config.modes || [ 'qa', 'compare', 'draft' ] ).forEach( function ( mode ) {
      var labelMap = { qa: '问答', compare: '对照', draft: '草稿生成' };
      modeSelect.appendChild( createEl( 'option', {
        value: mode,
        text: labelMap[ mode ] || mode
      } ) );
    } );

    ( config.detailLevels || [ 'intro', 'intermediate', 'research' ] ).forEach( function ( level ) {
      var labelMap = { intro: '入门', intermediate: '进阶', research: '研究' };
      detailSelect.appendChild( createEl( 'option', {
        value: level,
        text: labelMap[ level ] || level
      } ) );
    } );

    modeSelect.value = 'qa';

    function buildSettingsGrid( showFamilySelect ) {
      var fields = [];
      fields.push( createEl( 'label', {}, [ createEl( 'span', { text: '解释层级' } ), detailSelect ] ) );
      fields.push( createEl( 'label', { className: 'labassistant-settings-wide' }, [
        createEl( 'span', { text: '当前上下文页' } ),
        contextSummary || contextInput
      ] ) );
      if ( showFamilySelect ) {
        fields.push( createEl( 'label', {}, [ createEl( 'span', { text: '模型家族' } ), familySelect ] ) );
      }
      fields.push( createEl( 'label', {}, [ createEl( 'span', { text: '当前模型' } ), modelSelect ] ) );
      fields.push( createEl( 'label', { className: 'labassistant-settings-inline' }, [
        createEl( 'span', { text: '显示更多模型' } ),
        showAllToggle
      ] ) );
      return createEl( 'div', {
        className: showFamilySelect ? 'labassistant-settings-grid' : 'labassistant-settings-grid is-popover'
      }, fields );
    }

    var settingsPanel = variant === 'special' ? createEl( 'section', {
      className: 'labassistant-settings-panel'
    }, [
      buildSettingsGrid( true )
    ] ) : createEl( 'section', {
      className: 'labassistant-settings-panel',
      hidden: 'hidden'
    } );

    var drawerSettingsPopover = compactWorkspace ? createEl( 'section', {
      className: 'labassistant-settings-popover',
      hidden: 'hidden'
    }, [
      createEl( 'div', { className: 'labassistant-settings-popover-copy' }, [
        createEl( 'strong', { text: '对话选项' } ),
        createEl( 'span', {
          className: 'labassistant-status-note',
          text: '默认围绕当前页整理内容；这里只保留少量高级设置。'
        } )
      ] ),
      buildSettingsGrid( false )
    ] ) : null;
    var historySearchInput = createEl( 'input', {
      type: 'search',
      className: 'labassistant-history-search',
      placeholder: '搜索页面、问题或会话 ID'
    } );
    var historyStatus = createEl( 'div', {
      className: 'labassistant-history-status',
      text: '暂无历史会话。'
    } );
    var historyList = createEl( 'div', {
      className: 'labassistant-history-list'
    } );
    var historyPanel = createEl( 'section', {
      className: 'labassistant-history-panel',
      hidden: 'hidden'
    }, [
      createEl( 'div', { className: 'labassistant-history-header' }, [
        createEl( 'strong', { text: '历史会话 / 导出' } ),
        createEl( 'span', {
          className: 'labassistant-status-note',
          text: '搜索任意历史会话并导出 Markdown。'
        } )
      ] ),
      historySearchInput,
      historyStatus,
      historyList
    ] );

    var headerCopy = compactWorkspace ? createEl( 'div', {
      className: 'labassistant-header-copy is-compact'
    }, [
      createEl( 'h2', { text: '知识助手' } )
    ] ) : createEl( 'div', { className: 'labassistant-header-copy' }, [
      createEl( 'span', { className: 'labassistant-header-kicker', text: 'Advanced Workspace' } ),
      createEl( 'h2', { text: '知识助手' } ),
      createEl( 'div', { className: 'labassistant-badge-row' }, [
        sessionBadge,
        contextBadge,
        modelBadge
      ] )
    ] );

    var toolbarActions = createEl( 'div', { className: 'labassistant-toolbar-actions' }, (
      compactWorkspace ? [ historyButton, settingsButton, resetButton, closeButton ] : [ historyButton, settingsButton, resetButton, closeButton ]
    ).filter( Boolean ) );

    var headerTools = compactWorkspace ? createEl( 'div', {
      className: 'labassistant-toolbar-stack'
    }, [
      toolbarActions,
      drawerSettingsPopover
    ].filter( Boolean ) ) : toolbarActions;

    var header = createEl( 'header', { className: 'labassistant-header' }, [
      headerCopy,
      headerTools
    ] );
    var controlStack = createEl( 'div', {
      className: 'labassistant-control-stack',
      hidden: 'hidden'
    }, [
      settingsPanel,
      historyPanel
    ] );

    var composerChildren = [
      composerContextHint,
      attachmentRow,
      createEl( 'div', { className: 'labassistant-composer-shell' }, [
        questionInput,
        createEl( 'div', { className: 'labassistant-composer-row' }, [
          createEl( 'div', { className: 'labassistant-plus-stack' }, [
            plusButton,
            uploadMenu,
            imageUploadInput,
            documentUploadInput
          ] ),
          createEl( 'div', { className: 'labassistant-composer-row-spacer' } ),
          compactModelSelect,
          sendButton
        ] )
      ] )
    ];

    if ( variant === 'special' ) {
      composerChildren.push( createEl( 'div', { className: 'labassistant-composer-meta' }, [
        createEl( 'span', {
          className: 'labassistant-status-note',
          text: '更适合整理当前页、shot 和周实验日志草稿。'
        } )
      ] ) );
    }

    var composer = createEl( 'div', { className: 'labassistant-composer' }, composerChildren );

    function resizeQuestionInput() {
      questionInput.style.height = '0px';
      var nextHeight = Math.min( Math.max( questionInput.scrollHeight, 90 ), 210 );
      questionInput.style.height = nextHeight + 'px';
      questionInput.style.overflowY = questionInput.scrollHeight > nextHeight ? 'auto' : 'hidden';
    }

    function refreshLayoutState() {
      if ( variant === 'special' ) {
        settingsPanel.hidden = !state.showSettings;
        settingsPanel.style.display = state.showSettings ? 'grid' : 'none';
      } else {
        settingsPanel.hidden = true;
        settingsPanel.style.display = 'none';
        if ( drawerSettingsPopover ) {
          drawerSettingsPopover.hidden = !state.drawerPopoverOpen;
          drawerSettingsPopover.style.display = state.drawerPopoverOpen ? 'grid' : 'none';
        }
        if ( settingsButton ) {
          settingsButton.classList.toggle( 'is-active', state.drawerPopoverOpen );
        }
      }
      historyPanel.hidden = !state.historyOpen;
      historyPanel.style.display = state.historyOpen ? 'grid' : 'none';
      historyButton.classList.toggle( 'is-active', state.historyOpen );
      controlStack.hidden = !( ( variant === 'special' && state.showSettings ) || state.historyOpen );
      controlStack.style.display = controlStack.hidden ? 'none' : 'grid';
      if ( uploadMenu ) {
        uploadMenu.hidden = !state.uploadMenuOpen;
        uploadMenu.style.display = state.uploadMenuOpen ? 'grid' : 'none';
      }
    }

    function formatHistoryTimestamp( value ) {
      if ( !value ) {
        return '';
      }
      try {
        var date = new Date( value );
        if ( isNaN( date.getTime() ) ) {
          return '';
        }
        return date.toLocaleString( 'zh-CN', {
          hour12: false,
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit'
        } );
      } catch ( error ) {
        return '';
      }
    }

    function buildActiveHistoryEntry() {
      var lastTurn = state.turns.length ? state.turns[ state.turns.length - 1 ] : null;
      if ( !state.sessionId ) {
        return null;
      }
      return {
        session_id: state.sessionId,
        current_page: resolveEffectiveContextTitle( contextInput.value, config ) || config.currentTitle || '',
        latest_question: state.pendingQuestion || ( lastTurn && lastTurn.question ) || '',
        turn_count: state.turns.length + ( state.pendingQuestion ? 1 : 0 ),
        updated_at: new Date().toISOString(),
        synthetic: true
      };
    }

    function getHistoryDisplayItems() {
      var exportUtils = getSessionExportUtils();
      var items = exportUtils && exportUtils.normalizeSessionHistoryItems ?
        exportUtils.normalizeSessionHistoryItems( state.historySessions ) :
        ( state.historySessions || [] ).slice();
      var activeEntry = buildActiveHistoryEntry();
      if ( activeEntry && !items.some( function ( item ) {
        return item.session_id === activeEntry.session_id;
      } ) ) {
        items.unshift( activeEntry );
      }
      if ( exportUtils && exportUtils.filterSessionHistoryItems ) {
        return exportUtils.filterSessionHistoryItems( items, state.historyQuery );
      }
      return items;
    }

    function renderHistoryPanel() {
      var items = getHistoryDisplayItems();
      if ( historySearchInput.value !== state.historyQuery ) {
        historySearchInput.value = state.historyQuery;
      }
      clearNode( historyList );
      if ( state.historyLoading ) {
        historyStatus.textContent = '正在读取历史会话…';
        historyStatus.className = 'labassistant-history-status';
        return;
      }
      if ( state.historyError ) {
        historyStatus.textContent = state.historyError;
        historyStatus.className = 'labassistant-history-status is-error';
        return;
      }
      if ( state.historyNotice ) {
        historyStatus.textContent = state.historyNotice;
        historyStatus.className = 'labassistant-history-status is-success';
      } else if ( !items.length ) {
        historyStatus.textContent = state.historyQuery ? '没有匹配的历史会话。' : '暂无可导出的历史会话。';
        historyStatus.className = 'labassistant-history-status';
      } else {
        historyStatus.textContent = '共 ' + items.length + ' 条历史会话。';
        historyStatus.className = 'labassistant-history-status';
      }
      items.forEach( function ( item ) {
        var title = item.current_page || item.latest_question || ( '会话 ' + shortSessionId( item.session_id ) );
        var metaParts = [];
        var exportButton = createEl( 'button', {
          type: 'button',
          className: 'labassistant-toolbar-button',
          text: state.historyExportingSessionId === item.session_id ? '导出中…' : '导出 Markdown'
        } );
        if ( item.turn_count ) {
          metaParts.push( '轮次 ' + item.turn_count );
        }
        if ( item.updated_at ) {
          metaParts.push( '更新 ' + formatHistoryTimestamp( item.updated_at ) );
        }
        if ( item.session_id === state.sessionId ) {
          metaParts.push( '当前会话' );
        }
        exportButton.disabled = state.historyExportingSessionId === item.session_id;
        exportButton.addEventListener( 'click', function () {
          state.historyExportingSessionId = item.session_id;
          state.historyNotice = '';
          state.historyError = '';
          renderHistoryPanel();
          downloadSessionMarkdown( apiBase, item, config.userName || '' ).then( function ( filename ) {
            state.historyNotice = '已开始下载：' + filename;
          } ).catch( function ( error ) {
            state.historyError = error.message || 'Markdown 导出失败';
          } ).finally( function () {
            state.historyExportingSessionId = '';
            renderHistoryPanel();
          } );
        } );
        historyList.appendChild( createEl( 'article', {
          className: 'labassistant-history-item'
        }, [
          createEl( 'div', { className: 'labassistant-history-copy' }, [
            createEl( 'strong', { text: title } ),
            item.current_page && item.latest_question ? createEl( 'span', {
              className: 'labassistant-history-subtitle',
              text: item.latest_question
            } ) : null,
            createEl( 'span', {
              className: 'labassistant-history-meta',
              text: metaParts.join( ' · ' )
            } )
          ] ),
          exportButton
        ] ) );
      } );
    }

    function ensureHistorySessionsLoaded() {
      if ( state.historyLoading || state.historyLoaded ) {
        renderHistoryPanel();
        return Promise.resolve();
      }
      state.historyLoading = true;
      state.historyError = '';
      state.historyNotice = '';
      renderHistoryPanel();
      return loadSessionHistory( apiBase, config.userName || '' ).then( function ( body ) {
        state.historySessions = body.sessions || [];
        state.historyLoaded = true;
      } ).catch( function ( error ) {
        state.historyError = error.message || '历史会话读取失败';
      } ).finally( function () {
        state.historyLoading = false;
        renderHistoryPanel();
      } );
    }

    function buildTranscriptItems() {
      var items = [];
      state.turns.forEach( function ( turn ) {
        items.push( { role: 'user', text: turn.question || '' } );
        items.push( { role: 'assistant', result: turnToResult( turn ), isPending: false } );
      } );
      if ( state.pendingQuestion ) {
        items.push( { role: 'user', text: state.pendingQuestion, isPending: true } );
        items.push( { role: 'assistant', result: state.currentResult || { answer: '' }, isPending: true } );
      }
      return items;
    }

    function scrollTranscriptToBottom() {
      requestAnimationFrame( function () {
        transcript.scrollTop = transcript.scrollHeight;
      } );
    }

    function findGroup( family ) {
      var groups = ( state.modelCatalog && state.modelCatalog.groups ) || [];
      return groups.find( function ( item ) {
        return item.id === family;
      } ) || null;
    }

    function inferFamily( model ) {
      if ( !model ) {
        return state.selectedFamily || 'gpt';
      }
      if ( model.indexOf( 'claude-' ) === 0 ) {
        return 'claude';
      }
      if ( model.indexOf( 'gemini-' ) === 0 ) {
        return 'gemini';
      }
      return 'gpt';
    }

    function findSelectedModelItem() {
      var group = findGroup( state.selectedFamily );
      if ( !group ) {
        return null;
      }
      return ( group.items || [] ).find( function ( item ) {
        return item.id === state.selectedModel;
      } ) || null;
    }

    function persistModelSelection() {
      if ( state.selectedModel ) {
        localStorage.setItem( MODEL_STORAGE_KEY, state.selectedModel );
      }
      if ( state.selectedFamily ) {
        localStorage.setItem( MODEL_FAMILY_STORAGE_KEY, state.selectedFamily );
      }
    }

    function refreshSessionBadge() {
      sessionBadge.textContent = '会话：' + shortSessionId( state.sessionId );
    }

    function refreshContextBadge() {
      var contextTitle = resolveEffectiveContextTitle( contextInput.value, config );
      var explicitContext = contextInput.value.trim();
      if ( contextBadge ) {
        contextBadge.textContent = contextTitle ? ( '上下文：' + contextTitle ) : '上下文：未绑定页面';
      }
      composerContextHint.textContent = contextTitle ? ( '当前页：' + contextTitle ) : '当前页：自动识别';
      if ( contextSummary ) {
        contextSummary.textContent = explicitContext || contextTitle || '自动跟随当前页面';
        contextSummary.title = contextTitle || '';
      }
      if ( !state.turns.length && !state.pendingQuestion ) {
        renderTranscript();
      }
    }

    function refreshModelBadge( info ) {
      var selected;
      if ( info && info.resolved_model ) {
        modelBadge.textContent = '模型：' + info.resolved_model + ( info.fallback_applied ? '（已降级）' : '' );
        if ( compactModelSelect ) {
          compactModelSelect.value = info.requested_model || info.resolved_model;
        }
        return;
      }
      selected = findSelectedModelItem();
      modelBadge.textContent = '模型：' + ( selected ? selected.id : '未选择' );
      if ( compactModelSelect ) {
        compactModelSelect.value = selected ? selected.id : '';
      }
    }

    function setDrawerPopoverOpen( nextState ) {
      if ( !compactWorkspace ) {
        return;
      }
      state.drawerPopoverOpen = nextState;
      if ( nextState ) {
        state.uploadMenuOpen = false;
        state.historyOpen = false;
      }
      refreshLayoutState();
    }

    function setHistoryOpen( nextState ) {
      state.historyOpen = !!nextState;
      if ( state.historyOpen ) {
        state.uploadMenuOpen = false;
        if ( compactWorkspace ) {
          state.drawerPopoverOpen = false;
        }
        ensureHistorySessionsLoaded();
      }
      refreshLayoutState();
      renderHistoryPanel();
    }

    function setUploadMenuOpen( nextState ) {
      state.uploadMenuOpen = nextState;
      if ( nextState ) {
        state.drawerPopoverOpen = false;
        state.historyOpen = false;
      }
      refreshLayoutState();
    }

    function syncSelectedModelFromInfo( info ) {
      if ( !info || !info.requested_model ) {
        return;
      }
      state.selectedFamily = inferFamily( info.requested_model );
      state.selectedModel = info.requested_model;
      persistModelSelection();
    }

    function refreshModelSelectors() {
      familySelect.innerHTML = '';
      modelSelect.innerHTML = '';
      compactModelSelect.innerHTML = '';
      if ( !state.modelCatalog || !state.modelCatalog.groups ) {
        refreshModelBadge();
        return;
      }
      state.modelCatalog.groups.forEach( function ( group ) {
        familySelect.appendChild( createEl( 'option', {
          value: group.id,
          text: group.label
        } ) );
      } );
      if ( !state.selectedFamily ) {
        state.selectedFamily = state.modelCatalog.groups[ 0 ] ? state.modelCatalog.groups[ 0 ].id : 'gpt';
      }
      familySelect.value = state.selectedFamily;
      var activeGroup = findGroup( state.selectedFamily );
      if ( !activeGroup ) {
        refreshModelBadge();
        return;
      }
      state.modelCatalog.groups.forEach( function ( group ) {
        ( group.items || [] ).forEach( function ( item ) {
          compactModelSelect.appendChild( createEl( 'option', {
            value: item.id,
            text: group.label + ' · ' + item.label
          } ) );
        } );
      } );
      activeGroup.items.forEach( function ( item ) {
        modelSelect.appendChild( createEl( 'option', {
          value: item.id,
          text: item.recommended ? ( item.label + ' · 推荐' ) : item.label
        } ) );
      } );
      if ( !state.selectedModel || !( activeGroup.items || [] ).some( function ( item ) {
        return item.id === state.selectedModel;
      } ) ) {
        state.selectedModel = activeGroup.items[ 0 ] ? activeGroup.items[ 0 ].id : null;
      }
      modelSelect.value = state.selectedModel || '';
      showAllToggle.checked = state.showAllModels;
      persistModelSelection();
      refreshModelBadge();
    }

    function renderAttachments() {
      clearNode( attachmentRow );
      if ( !state.attachments.length ) {
        attachmentRow.hidden = true;
        attachmentRow.style.display = 'none';
        return;
      }
      attachmentRow.hidden = false;
      attachmentRow.style.display = 'flex';
      state.attachments.forEach( function ( item ) {
        var chip = createEl( 'div', {
          className: 'labassistant-attachment-chip' + ( item.status === 'error' ? ' is-error' : '' )
        } );
        chip.appendChild( createEl( 'span', {
          className: 'labassistant-attachment-kind',
          text: item.kind === 'image' ? '图片' : '文档'
        } ) );
        chip.appendChild( createEl( 'span', {
          className: 'labassistant-attachment-name',
          text: item.name
        } ) );
        if ( item.status === 'uploading' ) {
          chip.appendChild( createEl( 'span', {
            className: 'labassistant-attachment-status',
            text: '上传中'
          } ) );
        } else if ( item.status === 'error' ) {
          chip.appendChild( createEl( 'span', {
            className: 'labassistant-attachment-status',
            text: '失败'
          } ) );
        }
        if (
          item.id &&
          item.status !== 'uploading' &&
          String( item.mime_type || '' ).toLowerCase() === 'application/pdf'
        ) {
          var ingestButton = createEl( 'button', {
            type: 'button',
            className: 'labassistant-attachment-open',
            text: '分析写入'
          } );
          ingestButton.addEventListener( 'click', function () {
            startPdfIngestForAttachment( item );
          } );
          chip.appendChild( ingestButton );
          var openButton = createEl( 'button', {
            type: 'button',
            className: 'labassistant-attachment-open',
            text: '阅读'
          } );
          openButton.addEventListener( 'click', function () {
            var attachmentUtils = getAttachmentUtils();
            var url = attachmentUtils && attachmentUtils.buildAttachmentContentUrl ?
              attachmentUtils.buildAttachmentContentUrl( apiBase, item.id, window.location ) :
              apiBase.replace( /\/+$/, '' ) + '/attachments/' + encodeURIComponent( item.id ) + '/content';
            dispatchPdfReaderOpen( {
              source: {
                type: 'assistant_attachment',
                attachmentId: item.id,
                url: url,
                fileLabel: item.name,
                pageTitle: config.currentTitle || config.defaultContextTitle || ''
              }
            } );
          } );
          chip.appendChild( openButton );
        }
        var removeButton = createEl( 'button', {
          type: 'button',
          className: 'labassistant-attachment-remove',
          text: '×',
          'aria-label': '移除附件'
        } );
        removeButton.disabled = item.status === 'uploading';
        removeButton.addEventListener( 'click', function () {
          if ( item.id ) {
            deleteAttachment( apiBase, item.id ).catch( function () {} );
          }
          state.attachments = state.attachments.filter( function ( entry ) {
            return entry.clientId !== item.clientId;
          } );
          renderAttachments();
        } );
        chip.appendChild( removeButton );
        attachmentRow.appendChild( chip );
      } );
    }

    function maybePatchSessionModel() {
      var selected = findSelectedModelItem();
      if ( !state.sessionId || !selected ) {
        refreshModelBadge();
        return;
      }
      updateSessionModel( apiBase, state.sessionId, {
        generation_provider: selected.provider,
        generation_model: selected.id
      } ).then( function ( body ) {
        if ( body.model_info ) {
          syncSelectedModelFromInfo( body.model_info );
          refreshModelSelectors();
          refreshModelBadge( body.model_info );
        }
      } ).catch( function ( error ) {
        console.warn( error );
        modelBadge.textContent = '模型：切换失败';
      } );
    }

    function handleFilesSelected( files ) {
      Array.from( files || [] ).forEach( function ( file ) {
        var clientId = 'local-' + Date.now() + '-' + Math.random().toString( 16 ).slice( 2 );
        state.attachments.push( {
          clientId: clientId,
          id: null,
          kind: file.type && file.type.indexOf( 'image/' ) === 0 ? 'image' : 'document',
          name: file.name,
          mime_type: file.type || 'application/octet-stream',
          size_bytes: file.size || 0,
          status: 'uploading'
        } );
        renderAttachments();
        uploadAttachment( apiBase, file ).then( function ( body ) {
          state.attachments = state.attachments.map( function ( item ) {
            if ( item.clientId !== clientId ) {
              return item;
            }
            return {
              clientId: clientId,
              id: body.id,
              kind: body.kind,
              name: body.name,
              mime_type: body.mime_type,
              size_bytes: body.size_bytes,
              status: 'ready'
            };
          } );
          renderAttachments();
        } ).catch( function ( error ) {
          state.attachments = state.attachments.map( function ( item ) {
            if ( item.clientId !== clientId ) {
              return item;
            }
            item.status = 'error';
            item.error = error.message || '上传失败';
            return item;
          } );
          renderAttachments();
        } );
      } );
    }

    function appendTurnFromResponse( payload ) {
      state.turns.push( {
        session_id: payload.session_id || state.sessionId,
        turn_id: payload.turn_id,
        question: state.pendingQuestion,
        answer: payload.answer,
        mode: payload.mode || 'qa',
        task_type: payload.task_type,
        confidence: payload.confidence,
        step_stream: payload.step_stream || [],
        sources: payload.sources || [],
        unresolved_gaps: payload.unresolved_gaps || [],
        suggested_followups: payload.suggested_followups || [],
        action_trace: payload.action_trace || [],
        draft_preview: payload.draft_preview || null,
        draft_commit_result: payload.draft_commit_result || null,
        write_preview: payload.write_preview || null,
        write_result: payload.write_result || null,
        result_fill: payload.result_fill || null,
        pdf_ingest_review: payload.pdf_ingest_review || null,
        pdf_control_preview: payload.pdf_control_preview || null,
        pdf_control_commit_result: payload.pdf_control_commit_result || null,
        model_info: payload.model_info || null,
        form_fill_notice: payload.form_fill_notice || '',
        editor_fill_notice: payload.editor_fill_notice || ''
      } );
      state.historyLoaded = false;
      state.historyNotice = '';
      state.pendingQuestion = '';
      state.currentResult = null;
    }

    function persistResultNotice( result, key, value ) {
      var normalizedValue = String( value || '' );
      var matchedTurn;
      if ( result ) {
        result[ key ] = normalizedValue;
      }
      if (
        state.currentResult &&
        result &&
        state.currentResult.turn_id &&
        result.turn_id &&
        state.currentResult.turn_id === result.turn_id
      ) {
        state.currentResult[ key ] = normalizedValue;
      }
      matchedTurn = state.turns.find( function ( turn ) {
        return turn.turn_id && result && result.turn_id && turn.turn_id === result.turn_id;
      } );
      if ( matchedTurn ) {
        matchedTurn[ key ] = normalizedValue;
      }
    }

    function persistResultField( result, key, value ) {
      var matchedTurn;
      if ( result ) {
        result[ key ] = value;
      }
      if (
        state.currentResult &&
        result &&
        state.currentResult.turn_id &&
        result.turn_id &&
        state.currentResult.turn_id === result.turn_id
      ) {
        state.currentResult[ key ] = value;
      }
      matchedTurn = state.turns.find( function ( turn ) {
        return turn.turn_id && result && result.turn_id && turn.turn_id === result.turn_id;
      } );
      if ( matchedTurn ) {
        matchedTurn[ key ] = value;
      }
    }

    function getNormalizedFieldLabel( value ) {
      var currentEditorUtils = getEditorUtils();
      if ( currentEditorUtils && currentEditorUtils.normalizeFieldName ) {
        return currentEditorUtils.normalizeFieldName( value );
      }
      return String( value || '' ).trim().toLowerCase();
    }

    function persistResultFillMutation( result, mutateFn ) {
      var matchedTurn = state.turns.find( function ( turn ) {
        return turn.turn_id && result && result.turn_id && turn.turn_id === result.turn_id;
      } );
      var targets = [ result ];
      if (
        state.currentResult &&
        result &&
        state.currentResult.turn_id &&
        result.turn_id &&
        state.currentResult.turn_id === result.turn_id
      ) {
        targets.push( state.currentResult );
      }
      if ( matchedTurn && matchedTurn !== result && matchedTurn !== state.currentResult ) {
        targets.push( matchedTurn );
      }
      targets.forEach( function ( target ) {
        if ( target && target.result_fill ) {
          mutateFn( target.result_fill );
        }
      } );
    }

    function confirmPendingMatch( result, match ) {
      var normalizedFieldLabel = getNormalizedFieldLabel( match && match.fieldLabel );
      persistResultFillMutation( result, function ( resultFill ) {
        var suggestions = resultFill.field_suggestions || {};
        var suggestion = suggestions[ match.suggestionKey ];
        if ( suggestion && typeof suggestion === 'object' && !Array.isArray( suggestion ) ) {
          suggestion.status = 'confirmed';
        } else if ( typeof suggestion === 'string' && suggestion.trim() ) {
          suggestions[ match.suggestionKey ] = {
            value: suggestion.trim(),
            status: 'confirmed',
            evidence: []
          };
        }
        if ( Array.isArray( resultFill.missing_items ) ) {
          resultFill.missing_items = resultFill.missing_items.filter( function ( item ) {
            var label = item && typeof item === 'object' && !Array.isArray( item ) ?
              item.label || item.field || item.name :
              item;
            return getNormalizedFieldLabel( label ) !== normalizedFieldLabel;
          } );
        }
      } );
    }

    function getLatestSubmissionGuidanceResult() {
      if (
        state.currentResult &&
        (
          buildPendingFormDetails( state.currentResult ).length ||
          buildFormMissingFields( state.currentResult ).length ||
          state.currentResult.form_fill_notice ||
          state.currentResult.editor_fill_notice
        )
      ) {
        return state.currentResult;
      }
      return state.turns.slice().reverse().find( function ( turn ) {
        return (
          buildPendingFormDetails( turn ).length ||
          buildFormMissingFields( turn ).length ||
          turn.form_fill_notice ||
          turn.editor_fill_notice
        );
      } ) || null;
    }

    function buildPendingFormDetails( result ) {
      var editorUtils = getEditorUtils();
      var fieldSections;
      if ( !editorUtils || !editorUtils.buildResultFillFieldSections ) {
        return [];
      }
      fieldSections = editorUtils.buildResultFillFieldSections(
        buildFormSuggestionMap( result ),
        buildFormMissingDetails( result )
      );
      return ( fieldSections.pending || [] ).map( function ( entry ) {
        return {
          label: entry.label,
          reason: entry.reason || '',
          evidence: Array.isArray( entry.evidence ) ? entry.evidence.slice() : []
        };
      } );
    }

    function publishSubmissionGuidance() {
      var contextTitle = resolveEffectiveContextTitle( contextInput.value, config );
      var result = getLatestSubmissionGuidanceResult();
      var pendingItems = result ? buildPendingFormDetails( result ) : [];
      var missingItems = result ? buildFormMissingDetails( result ) : [];
      var pendingNames = pendingItems.map( function ( entry ) {
        return getNormalizedFieldLabel( entry.label );
      } );
      var detail = {
        contextTitle: contextTitle,
        editorMode: editorMode,
        pendingItems: pendingItems,
        missingItems: missingItems.filter( function ( entry ) {
          return pendingNames.indexOf( getNormalizedFieldLabel( entry.label ) ) === -1;
        } ),
        formFillNotice: result && result.form_fill_notice ? result.form_fill_notice : '',
        editorFillNotice: result && result.editor_fill_notice ? result.editor_fill_notice : ''
      };
      if ( window.sessionStorage && contextTitle ) {
        var key = getSubmissionGuidanceKey( contextTitle, window.location.host );
        if (
          detail.pendingItems.length ||
          detail.missingItems.length ||
          detail.formFillNotice ||
          detail.editorFillNotice
        ) {
          sessionStorage.setItem( key, JSON.stringify( detail ) );
        } else {
          sessionStorage.removeItem( key );
        }
      }
      window.dispatchEvent( new CustomEvent( 'labassistant:submission-guidance', {
        detail: detail
      } ) );
    }

    function renderSources( result ) {
      var list = createEl( 'div', { className: 'labassistant-evidence-list' } );
      ( result.sources || [] ).forEach( function ( source ) {
        var title = source.title || source.source_id || '来源';
        var url = normalizeSourceUrl( source.url );
        var head = createEl( 'div', { className: 'labassistant-evidence-head' }, [
          url
            ? createEl( 'a', { href: url, target: '_blank', rel: 'noopener', text: title } )
            : createEl( 'strong', { text: title } )
        ] );
        if ( source.source_type ) {
          head.appendChild( createEl( 'span', {
            className: 'labassistant-source-chip',
            text: source.source_type
          } ) );
        }
        list.appendChild( createEl( 'article', { className: 'labassistant-evidence-item' }, [
          head,
          createEl( 'span', {
            className: 'labassistant-evidence-meta',
            text: source.snippet || ''
          } )
        ] ) );
      } );
      return list;
    }

    function renderSteps( result ) {
      var list = createEl( 'div', { className: 'labassistant-step-list' } );
      ( result.step_stream || [] ).forEach( function ( step ) {
        list.appendChild( createEl( 'div', { className: 'labassistant-step-item is-' + ( step.status || 'waiting' ) }, [
          createEl( 'span', { className: 'labassistant-step-dot', 'aria-hidden': 'true' } ),
          createEl( 'div', { className: 'labassistant-step-copy' }, [
            createEl( 'strong', { text: step.title || step.stage || '步骤' } ),
            createEl( 'span', { className: 'labassistant-status-note', text: [ step.status, step.detail ].filter( Boolean ).join( ' · ' ) } )
          ] )
        ] ) );
      } );
      return list;
    }

    function renderActions( result ) {
      var list = createEl( 'div', { className: 'labassistant-step-list' } );
      ( result.action_trace || [] ).forEach( function ( action ) {
        list.appendChild( createEl( 'div', { className: 'labassistant-step-item is-action' }, [
          createEl( 'span', { className: 'labassistant-step-dot', 'aria-hidden': 'true' } ),
          createEl( 'div', { className: 'labassistant-step-copy' }, [
            createEl( 'strong', { text: action.action || '动作' } ),
            createEl( 'span', { className: 'labassistant-status-note', text: [ action.status, action.summary ].filter( Boolean ).join( ' · ' ) } )
          ] )
        ] ) );
      } );
      return list;
    }

    function getPageFormMatches( result ) {
      var pageFormContext = getPageFormRuntimeContext();
      var suggestions;
      if (
        pageFormContext.editorMode !== 'pageforms_edit' ||
        !pageFormContext.resolvedFormName ||
        !pageFormContext.pageFormFields.length ||
        !editorUtils ||
        !editorUtils.matchStructuredFieldsToInventory
      ) {
        return [];
      }
      suggestions = buildFormSuggestionMap( result );
      return editorUtils.matchStructuredFieldsToInventory(
        pageFormContext.resolvedFormName,
        suggestions,
        pageFormContext.pageFormFields
      ).map( function ( match ) {
        var field = pageFormContext.pageFormFields.find( function ( item ) {
          return item.key === match.fieldKey;
        } );
        match.field = field || null;
        return match;
      } );
    }

    function renderPageFormFillCard( result, rerender ) {
      var matches = getPageFormMatches( result );
      var editorUtils = getEditorUtils();
      var missingDetails = buildFormMissingDetails( result );
      var fieldSections = editorUtils && editorUtils.buildResultFillFieldSections ?
        editorUtils.buildResultFillFieldSections(
          buildFormSuggestionMap( result ),
          buildFormMissingFields( result )
        ) :
        { missing: buildFormMissingFields( result ) };
      var safeMatches = matches.filter( function ( match ) {
        return match.status !== 'pending' && match.status !== 'needs_review';
      } );
      var pendingMatches = matches.filter( function ( match ) {
        return match.status === 'pending' || match.status === 'needs_review';
      } );
      var missingFields = fieldSections.missing || buildFormMissingFields( result );
      var fillAllButton;
      if ( !safeMatches.length && !pendingMatches.length && !missingFields.length ) {
        return null;
      }

      var card = createEl( 'div', { className: 'labassistant-inline-card labassistant-form-fill-card' } );

      card.appendChild( createEl( 'h4', { text: '表单字段建议' } ) );
      card.appendChild( createEl( 'div', {
        className: 'labassistant-status-note',
        text: safeMatches.length ?
          (
            '已安全匹配 ' + safeMatches.length + ' 个字段；只填可安全匹配的控件。' +
            ( pendingMatches.length ? ( ' 另有 ' + pendingMatches.length + ' 个字段待人工确认。' ) : '' )
          ) :
          (
            pendingMatches.length ?
              '当前没有可安全自动填入的字段；已有候选值的字段需要学生先确认。' :
              '当前没有可安全自动填入的字段。'
          )
      } ) );

      if ( safeMatches.length ) {
        fillAllButton = createEl( 'button', {
          type: 'button',
          className: 'labassistant-inline-button',
          text: '一键填入全部已匹配字段'
        } );
        fillAllButton.addEventListener( 'click', function () {
          var appliedCount = 0;
          var appliedMatches = [];
          var notice;
          safeMatches.forEach( function ( match ) {
            if ( applyPageFormMatch( match ) ) {
              appliedCount += 1;
              appliedMatches.push( match );
            }
          } );
          notice = editorUtils && editorUtils.buildFormFillNotice ?
            editorUtils.buildFormFillNotice( appliedMatches ) :
            ( appliedCount ? ( '已填入 ' + appliedCount + ' 个表单字段，表单尚未提交。' ) : '没有可填入的字段。' );
          persistResultNotice( result, 'form_fill_notice', notice );
          rerender();
        } );
        card.appendChild( fillAllButton );
      }

      safeMatches.forEach( function ( match ) {
        var item = createEl( 'div', { className: 'labassistant-form-fill-item' } );
        var valueText = Array.isArray( match.value ) ? match.value.join( '；' ) : match.value;
        var fillButton = createEl( 'button', {
          type: 'button',
          className: 'labassistant-inline-button labassistant-inline-button-secondary',
          text: '填入此字段'
        } );
        fillButton.addEventListener( 'click', function () {
          var notice;
          if ( applyPageFormMatch( match ) ) {
            notice = editorUtils && editorUtils.buildFormFillNotice ?
              editorUtils.buildFormFillNotice( [ match ] ) :
              ( '已填入字段：' + match.fieldLabel + '；表单尚未提交。' );
            persistResultNotice( result, 'form_fill_notice', notice );
            rerender();
          }
        } );

        item.appendChild( createEl( 'div', { className: 'labassistant-form-fill-copy' }, [
          createEl( 'strong', { text: match.fieldLabel } ),
          createEl( 'span', { className: 'labassistant-status-note', text: valueText } )
        ] ) );
        if ( match.evidence && match.evidence.length ) {
          item.appendChild( createEl( 'div', { className: 'labassistant-form-missing-list' },
            match.evidence.map( function ( evidenceItem ) {
              return createEl( 'span', {
                className: 'labassistant-form-missing-chip',
                text: evidenceItem
              } );
            } )
          ) );
        }
        item.appendChild( fillButton );
        card.appendChild( item );
      } );

      if ( pendingMatches.length ) {
        var pendingSection = createEl( 'section', { className: 'labassistant-form-missing' }, [
          createEl( 'div', { className: 'labassistant-form-missing-head' }, [
            createEl( 'strong', { text: '待确认字段' } ),
            createEl( 'span', {
              className: 'labassistant-status-note',
              text: '这些字段已有候选值，但默认不自动填入。'
            } )
          ] )
        ] );
        pendingMatches.forEach( function ( match ) {
          var confirmButton = createEl( 'button', {
            type: 'button',
            className: 'labassistant-inline-button labassistant-inline-button-secondary',
            text: '确认并填入此字段'
          } );
          var pendingItem = createEl( 'div', { className: 'labassistant-form-fill-item' }, [
            createEl( 'div', { className: 'labassistant-form-fill-copy' }, [
              createEl( 'strong', { text: match.fieldLabel } ),
              createEl( 'span', {
                className: 'labassistant-status-note',
                text: Array.isArray( match.value ) ? match.value.join( '；' ) : match.value
              } ),
              match.reason ? createEl( 'span', {
                className: 'labassistant-status-note',
                text: match.reason
              } ) : null
            ] )
          ] );
          if ( match.evidence && match.evidence.length ) {
            pendingItem.appendChild( createEl( 'div', { className: 'labassistant-form-missing-list' },
              match.evidence.map( function ( evidenceItem ) {
                return createEl( 'span', {
                  className: 'labassistant-form-missing-chip',
                  text: evidenceItem
              } );
            } )
          ) );
          }
          confirmButton.addEventListener( 'click', function () {
            var notice;
            if ( applyPageFormMatch( match ) ) {
              confirmPendingMatch( result, match );
              notice = editorUtils && editorUtils.buildFormFillNotice ?
                editorUtils.buildFormFillNotice( [ match ] ) :
                ( '已确认并填入字段：' + match.fieldLabel + '；表单尚未提交。' );
              persistResultNotice( result, 'form_fill_notice', notice );
              rerender();
            }
          } );
          pendingItem.appendChild( confirmButton );
          pendingSection.appendChild( pendingItem );
        } );
        card.appendChild( pendingSection );
      }

      if ( missingFields.length ) {
        var resolvedMissingDetails = missingDetails.filter( function ( entry ) {
          return missingFields.indexOf( entry.label ) !== -1;
        } );
        var missingSection = createEl( 'section', { className: 'labassistant-form-missing' }, [
          createEl( 'div', { className: 'labassistant-form-missing-head' }, [
            createEl( 'strong', { text: '缺失字段' } ),
            createEl( 'span', {
              className: 'labassistant-status-note',
              text: '这些字段暂不自动填入。'
            } )
          ] )
        ] );
        if ( resolvedMissingDetails.some( function ( entry ) {
          return entry.reason || ( entry.evidence && entry.evidence.length );
        } ) ) {
          resolvedMissingDetails.forEach( function ( entry ) {
            var missingItem = createEl( 'div', { className: 'labassistant-form-fill-item' }, [
              createEl( 'div', { className: 'labassistant-form-fill-copy' }, [
                createEl( 'strong', { text: entry.label } ),
                createEl( 'span', {
                  className: 'labassistant-status-note',
                  text: entry.reason || '当前没有可直接回填的候选值。'
                } )
              ] )
            ] );
            if ( entry.evidence && entry.evidence.length ) {
              missingItem.appendChild( createEl( 'div', { className: 'labassistant-form-missing-list' },
                entry.evidence.map( function ( evidenceItem ) {
                  return createEl( 'span', {
                    className: 'labassistant-form-missing-chip',
                    text: evidenceItem
                  } );
                } )
              ) );
            }
            missingSection.appendChild( missingItem );
          } );
        } else {
          missingSection.appendChild( createEl( 'div', { className: 'labassistant-form-missing-list' },
            missingFields.map( function ( fieldName ) {
              return createEl( 'span', {
                className: 'labassistant-form-missing-chip',
                text: fieldName
              } );
            } )
          ) );
        }
        card.appendChild( missingSection );
      }

      if ( result.form_fill_notice ) {
        card.appendChild( createEl( 'div', {
          className: 'labassistant-callout',
          text: result.form_fill_notice
        } ) );
      }

      return card;
    }

    function renderResultFillCard( result, rerender ) {
      var payload = result && result.result_fill;
      var editorUtils = getEditorUtils();
      var missingDetails = buildFormMissingDetails( result );
      var fieldSections = editorUtils && editorUtils.buildResultFillFieldSections ?
        editorUtils.buildResultFillFieldSections(
          payload && payload.field_suggestions ? payload.field_suggestions : {},
          payload && payload.missing_items ? payload.missing_items : []
        ) :
        { confirmed: [], pending: [], missing: buildFormMissingFields( result ) };
      var evidenceList;
      var fillButton;
      var missingSection;
      if ( !payload ) {
        return null;
      }

      function createFieldSection( title, note, entries ) {
        var section;
        if ( !entries.length ) {
          return null;
        }
        section = createEl( 'section', { className: 'labassistant-form-missing' }, [
          createEl( 'div', { className: 'labassistant-form-missing-head' }, [
            createEl( 'strong', { text: title } ),
            createEl( 'span', { className: 'labassistant-status-note', text: note } )
          ] )
        ] );
        entries.forEach( function ( entry ) {
          var fieldItem = createEl( 'div', { className: 'labassistant-form-fill-item' }, [
            createEl( 'div', { className: 'labassistant-form-fill-copy' }, [
              createEl( 'strong', { text: entry.label } ),
              createEl( 'span', { className: 'labassistant-status-note', text: entry.value } ),
              entry.reason ? createEl( 'span', {
                className: 'labassistant-status-note',
                text: entry.reason
              } ) : null
            ] )
          ] );
          if ( entry.evidence && entry.evidence.length ) {
            fieldItem.appendChild( createEl( 'div', { className: 'labassistant-form-missing-list' },
              entry.evidence.map( function ( item ) {
                return createEl( 'span', {
                  className: 'labassistant-form-missing-chip',
                  text: item
                } );
              } )
            ) );
          }
          section.appendChild( fieldItem );
        } );
        return section;
      }

      var card = createEl( 'div', { className: 'labassistant-inline-card labassistant-form-fill-card' } );
      card.appendChild( createEl( 'h4', { text: payload.title || '结果回填建议' } ) );

      if ( payload.evidence && payload.evidence.length ) {
        evidenceList = createEl( 'div', { className: 'labassistant-form-missing-list' },
          payload.evidence.map( function ( item ) {
            return createEl( 'span', {
              className: 'labassistant-form-missing-chip',
              text: item
            } );
          } )
        );
        card.appendChild( createEl( 'div', { className: 'labassistant-status-note', text: '识别依据' } ) );
        card.appendChild( evidenceList );
      }

      var confirmedSection = createFieldSection(
        '已识别字段',
        '这些字段有明确候选值，可直接供学生核对。',
        fieldSections.confirmed
      );
      if ( confirmedSection ) {
        card.appendChild( confirmedSection );
      }

      var pendingFieldSection = createFieldSection(
        '待确认字段',
        '这些字段已有候选值，但还不能视为已确认。',
        fieldSections.pending
      );
      if ( pendingFieldSection ) {
        card.appendChild( pendingFieldSection );
      }

      if ( payload.draft_text ) {
        card.appendChild( createEl( 'div', {
          className: 'labassistant-markdown',
          html: renderMarkdown( payload.draft_text )
        } ) );
      }

      if ( editorTextarea && payload.draft_text ) {
        fillButton = createEl( 'button', {
          type: 'button',
          className: 'labassistant-inline-button',
          text: '把这版结果草稿填入编辑框'
        } );
        fillButton.addEventListener( 'click', function () {
          fillEditorWithText( result, payload.draft_text || '', rerender );
        } );
        card.appendChild( fillButton );
      }

      if ( fieldSections.missing && fieldSections.missing.length ) {
        var resolvedMissingDetails = missingDetails.filter( function ( entry ) {
          return fieldSections.missing.indexOf( entry.label ) !== -1;
        } );
        missingSection = createEl( 'section', { className: 'labassistant-form-missing' }, [
          createEl( 'div', { className: 'labassistant-form-missing-head' }, [
            createEl( 'strong', { text: '缺失字段' } ),
            createEl( 'span', {
              className: 'labassistant-status-note',
              text: '这些字段当前还没有可用候选值。'
            } )
          ] )
        ] );
        if ( resolvedMissingDetails.some( function ( entry ) {
          return entry.reason || ( entry.evidence && entry.evidence.length );
        } ) ) {
          resolvedMissingDetails.forEach( function ( entry ) {
            var missingItem = createEl( 'div', { className: 'labassistant-form-fill-item' }, [
              createEl( 'div', { className: 'labassistant-form-fill-copy' }, [
                createEl( 'strong', { text: entry.label } ),
                createEl( 'span', {
                  className: 'labassistant-status-note',
                  text: entry.reason || '当前没有可直接回填的候选值。'
                } )
              ] )
            ] );
            if ( entry.evidence && entry.evidence.length ) {
              missingItem.appendChild( createEl( 'div', { className: 'labassistant-form-missing-list' },
                entry.evidence.map( function ( evidenceItem ) {
                  return createEl( 'span', {
                    className: 'labassistant-form-missing-chip',
                    text: evidenceItem
                  } );
                } )
              ) );
            }
            missingSection.appendChild( missingItem );
          } );
        } else {
          missingSection.appendChild( createEl( 'div', { className: 'labassistant-form-missing-list' },
            fieldSections.missing.map( function ( item ) {
              return createEl( 'span', {
                className: 'labassistant-form-missing-chip',
                text: item
              } );
            } )
          ) );
        }
        card.appendChild( missingSection );
      }

      return card;
    }

    function renderPdfIngestReviewCard( result, rerender ) {
      var review = result && result.pdf_ingest_review;
      if ( !review ) {
        return null;
      }

      var card = createEl( 'div', { className: 'labassistant-inline-card labassistant-form-fill-card' } );
      var counts = [];
      if ( review.extracted_page_count ) {
        counts.push( '提取页数 ' + review.extracted_page_count );
      }
      if ( review.staged_image_count ) {
        counts.push( '页图 ' + review.staged_image_count );
      }

      card.appendChild( createEl( 'h4', { text: review.title || 'PDF 解析与写入建议' } ) );
      if ( review.file_name ) {
        card.appendChild( createEl( 'div', {
          className: 'labassistant-status-note',
          text: review.file_name + ( counts.length ? ' · ' + counts.join( ' · ' ) : '' )
        } ) );
      } else if ( counts.length ) {
        card.appendChild( createEl( 'div', {
          className: 'labassistant-status-note',
          text: counts.join( ' · ' )
        } ) );
      }

      if ( review.document_summary ) {
        card.appendChild( createEl( 'div', {
          className: 'labassistant-markdown',
          html: renderMarkdown( review.document_summary )
        } ) );
      }

      if ( review.recommended_targets && review.recommended_targets.length ) {
        var targetsSection = createEl( 'section', { className: 'labassistant-form-missing' }, [
          createEl( 'div', { className: 'labassistant-form-missing-head' }, [
            createEl( 'strong', { text: '建议归档区域' } ),
            createEl( 'span', {
              className: 'labassistant-status-note',
              text: '先写入草稿页，正式归档区域只作为推荐。'
            } )
          ] )
        ] );
        review.recommended_targets.slice( 0, 3 ).forEach( function ( item ) {
          var label = String( item.target_title || item.target_type || '' );
          var scoreText = item.score || item.score === 0 ? '匹配度 ' + Math.round( Number( item.score ) * 100 ) + '%' : '';
          targetsSection.appendChild( createEl( 'div', { className: 'labassistant-form-fill-item' }, [
            createEl( 'div', { className: 'labassistant-form-fill-copy' }, [
              createEl( 'strong', { text: label } ),
              createEl( 'span', {
                className: 'labassistant-status-note',
                text: [ item.reason || '', scoreText ].filter( Boolean ).join( ' · ' )
              } )
            ] )
          ] ) );
        } );
        card.appendChild( targetsSection );
      }

      if ( review.section_outline && review.section_outline.length ) {
        var outlineSection = createEl( 'section', { className: 'labassistant-form-missing' }, [
          createEl( 'div', { className: 'labassistant-form-missing-head' }, [
            createEl( 'strong', { text: '提取章节' } ),
            createEl( 'span', {
              className: 'labassistant-status-note',
              text: '这版会写进草稿页，方便后续拆到正式区域。'
            } )
          ] )
        ] );
        review.section_outline.slice( 0, 6 ).forEach( function ( item ) {
          outlineSection.appendChild( createEl( 'div', { className: 'labassistant-form-fill-item' }, [
            createEl( 'div', { className: 'labassistant-form-fill-copy' }, [
              createEl( 'strong', { text: item.title || '未命名章节' } ),
              createEl( 'span', {
                className: 'labassistant-status-note',
                text: item.content || ''
              } )
            ] )
          ] ) );
        } );
        card.appendChild( outlineSection );
      }

      if ( review.evidence && review.evidence.length ) {
        card.appendChild( createEl( 'div', { className: 'labassistant-form-missing-list' },
          review.evidence.map( function ( item ) {
            return createEl( 'span', {
              className: 'labassistant-form-missing-chip',
              text: item
            } );
          } )
        ) );
      }

      if ( review.needs_confirmation !== false ) {
        card.appendChild( createEl( 'div', {
          className: 'labassistant-callout',
          text: '确认后才会生成草稿预览并写入知识助手草稿页，不会直接改正式 Control: 或设备条目页面。'
        } ) );
      }

      if ( !result.draft_preview ) {
        var previewButton = createEl( 'button', {
          type: 'button',
          className: 'labassistant-inline-button',
          text: '生成草稿预览'
        } );
        previewButton.addEventListener( 'click', function () {
          previewButton.disabled = true;
          requestPdfDraftPreview( apiBase, {
            attachment_id: review.source_attachment_id,
            session_id: result.session_id || state.sessionId || null,
            turn_id: result.turn_id || null,
            review: review
          } ).then( function ( body ) {
            persistResultField( result, 'draft_preview', body );
            rerender();
          } ).catch( function ( error ) {
            alert( error.message || 'PDF 草稿预览生成失败' );
          } ).finally( function () {
            previewButton.disabled = false;
          } );
        } );
        card.appendChild( previewButton );
      } else {
        card.appendChild( createEl( 'div', {
          className: 'labassistant-callout',
          text: '草稿预览已生成：' + ( result.draft_preview.target_page || result.draft_preview.title || '知识助手草稿页' )
        } ) );
        if ( !result.draft_commit_result ) {
          var commitButton = createEl( 'button', {
            type: 'button',
            className: 'labassistant-inline-button',
            text: '确认写入草稿页'
          } );
          commitButton.addEventListener( 'click', function () {
            commitDraftPreview( result, rerender, commitButton, 'PDF 草稿提交失败' ).catch( function ( error ) {
              alert( error.message || 'PDF 草稿提交失败' );
            } );
          } );
          card.appendChild( commitButton );
        }
      }

      if ( result.draft_commit_result ) {
        card.appendChild( createEl( 'div', {
          className: 'labassistant-callout',
          text: '已写入草稿页：' + result.draft_commit_result.page_title
        } ) );
        if ( !result.pdf_control_preview ) {
          var formalPreviewButton = createEl( 'button', {
            type: 'button',
            className: 'labassistant-inline-button labassistant-inline-button-secondary',
            text: '生成 Control 正式写入预览'
          } );
          formalPreviewButton.addEventListener( 'click', function () {
            formalPreviewButton.disabled = true;
            requestPdfControlPreview( apiBase, {
              draft_preview_id: result.draft_preview && result.draft_preview.preview_id
            } ).then( function ( body ) {
              persistResultField( result, 'pdf_control_preview', body );
              rerender();
            } ).catch( function ( error ) {
              alert( error.message || 'Control 正式写入预览生成失败' );
            } ).finally( function () {
              formalPreviewButton.disabled = false;
            } );
          } );
          card.appendChild( formalPreviewButton );
        }
      }

      return card;
    }

    function renderPdfControlPreviewCard( result, rerender ) {
      var preview = result && result.pdf_control_preview;
      if ( !preview ) {
        return null;
      }

      var ingestUtils = getPdfIngestUtils();
      if ( ingestUtils && ingestUtils.normalizePdfControlPreview ) {
        preview = ingestUtils.normalizePdfControlPreview( preview );
      }
      if ( !preview ) {
        return null;
      }

      var card = createEl( 'div', { className: 'labassistant-inline-card labassistant-form-fill-card' } );
      card.appendChild( createEl( 'h4', { text: preview.target_page || 'Control 正式写入预览' } ) );
      card.appendChild( createEl( 'div', {
        className: 'labassistant-status-note',
        text: '总览挂载页：' + ( preview.overview_page || 'Control:控制与运行总览' )
      } ) );
      if ( preview.content ) {
        card.appendChild( createEl( 'div', {
          className: 'labassistant-markdown',
          html: renderMarkdown( preview.content )
        } ) );
      }
      if ( preview.overview_update ) {
        card.appendChild( createEl( 'section', { className: 'labassistant-form-missing' }, [
          createEl( 'div', { className: 'labassistant-form-missing-head' }, [
            createEl( 'strong', { text: '总览页入口预览' } )
          ] ),
          createEl( 'div', {
            className: 'labassistant-markdown',
            html: renderMarkdown( preview.overview_update )
          } )
        ] ) );
      }
      if ( preview.blocked_items && preview.blocked_items.length ) {
        var blockedSection = createEl( 'section', { className: 'labassistant-form-missing' }, [
          createEl( 'div', { className: 'labassistant-form-missing-head' }, [
            createEl( 'strong', { text: '已拦截的受限信息' } ),
            createEl( 'span', {
              className: 'labassistant-status-note',
              text: '这些内容不会写入普通 Control: 页。'
            } )
          ] )
        ] );
        preview.blocked_items.forEach( function ( item ) {
          blockedSection.appendChild( createEl( 'div', { className: 'labassistant-form-fill-item' }, [
            createEl( 'div', { className: 'labassistant-form-fill-copy' }, [
              createEl( 'strong', { text: item.label || '未命名章节' } ),
              createEl( 'span', {
                className: 'labassistant-status-note',
                text: [ item.reason || '', item.content || '' ].filter( Boolean ).join( ' · ' )
              } )
            ] )
          ] ) );
        } );
        card.appendChild( blockedSection );
      }

      if ( !result.pdf_control_commit_result ) {
        var commitButton = createEl( 'button', {
          type: 'button',
          className: 'labassistant-inline-button',
          text: '确认写入 Control 正式页'
        } );
        commitButton.addEventListener( 'click', function () {
          commitButton.disabled = true;
          commitPdfControlPreview( apiBase, preview.preview_id ).then( function ( body ) {
            persistResultField( result, 'pdf_control_commit_result', body );
            rerender();
          } ).catch( function ( error ) {
            alert( error.message || 'Control 正式写入失败' );
          } ).finally( function () {
            commitButton.disabled = false;
          } );
        } );
        card.appendChild( commitButton );
      } else {
        card.appendChild( createEl( 'div', {
          className: 'labassistant-callout',
          text: '已写入正式页：' + result.pdf_control_commit_result.page_title + '；已更新总览页：' + result.pdf_control_commit_result.overview_page
        } ) );
      }

      return card;
    }

    function renderVisualEditorHandoffCard( result, rerender ) {
      var content = '';
      if ( editorMode !== 'visual_editor' ) {
        return null;
      }
      content = ( result.draft_preview && result.draft_preview.content ) ||
        ( result.write_preview && result.write_preview.preview_text ) ||
        result.answer || '';
      if ( !content ) {
        return null;
      }
      var card = createEl( 'div', { className: 'labassistant-inline-card' } );
      var handoffButton = createEl( 'button', {
        type: 'button',
        className: 'labassistant-inline-button',
        text: '切到源码编辑并填入草稿'
      } );
      handoffButton.addEventListener( 'click', function () {
        navigateToSourceEdit( config, content, result );
      } );
      card.appendChild( createEl( 'h4', { text: '源码编辑联动' } ) );
      card.appendChild( createEl( 'div', {
        className: 'labassistant-status-note',
        text: '将切到源码编辑页并预填草稿；不会自动保存页面。'
      } ) );
      card.appendChild( handoffButton );
      return card;
    }

    function fillEditorWithText( result, content, rerender ) {
      if ( !editorTextarea || !content ) {
        return false;
      }
      if ( editorTextarea.value.trim() && !window.confirm( '这会替换当前编辑框内容，但不会自动保存页面。继续吗？' ) ) {
        return false;
      }
      editorTextarea.value = content;
      editorTextarea.dispatchEvent( new Event( 'input', { bubbles: true } ) );
      editorTextarea.dispatchEvent( new Event( 'change', { bubbles: true } ) );
      editorTextarea.focus();
      editorTextarea.scrollTop = 0;
      if ( result ) {
        persistResultNotice( result, 'editor_fill_notice', '已填入当前编辑框，页面尚未保存。' );
      }
      if ( rerender ) {
        rerender();
      }
      return true;
    }

    function commitDraftPreview( result, rerender, button, errorMessage ) {
      var commitButton = button || null;
      if ( !result || !result.draft_preview || !result.draft_preview.preview_id ) {
        return Promise.reject( new Error( errorMessage || '草稿预览不存在。' ) );
      }
      if ( commitButton ) {
        commitButton.disabled = true;
      }
      return fetch( apiBase + '/draft/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify( {
          preview_id: result.draft_preview.preview_id
        } )
      } ).then( function ( response ) {
        return response.json().then( function ( body ) {
          if ( !response.ok ) {
            throw new Error( body.detail || errorMessage || '提交失败' );
          }
          persistResultField( result, 'draft_commit_result', body );
          rerender();
          return body;
        } );
      } ).finally( function () {
        if ( commitButton ) {
          commitButton.disabled = false;
        }
      } );
    }

    function renderCommitCard( result, rerender ) {
      var card = createEl( 'div', { className: 'labassistant-inline-card' } );

      if ( result.draft_preview ) {
        card.appendChild( createEl( 'h4', { text: result.draft_preview.title || '页面草稿' } ) );
        card.appendChild( createEl( 'div', {
          className: 'labassistant-markdown',
          html: renderMarkdown( result.draft_preview.content || '' )
        } ) );
        if ( editorMode === 'visual_editor' ) {
          var handoffDraftButton = createEl( 'button', {
            type: 'button',
            className: 'labassistant-inline-button',
            text: '切到源码编辑并填入草稿'
          } );
          handoffDraftButton.addEventListener( 'click', function () {
            navigateToSourceEdit( config, result.draft_preview.content || '', result );
          } );
          card.appendChild( handoffDraftButton );
        }
        if ( editorTextarea ) {
          var fillDraftButton = createEl( 'button', {
            type: 'button',
            className: 'labassistant-inline-button labassistant-inline-button-secondary',
            text: '填入编辑框'
          } );
          fillDraftButton.addEventListener( 'click', function () {
            fillEditorWithText( result, result.draft_preview.content || '', rerender );
          } );
          card.appendChild( fillDraftButton );
        }
        var commitDraftButton = createEl( 'button', {
          type: 'button',
          className: 'labassistant-inline-button',
          text: '确认写入草稿页'
        } );
        commitDraftButton.addEventListener( 'click', function () {
          commitDraftPreview( result, rerender, commitDraftButton, '提交失败' ).catch( function ( error ) {
            alert( error.message || '提交失败' );
          } );
        } );
        card.appendChild( commitDraftButton );
        if ( result.draft_commit_result ) {
          card.appendChild( createEl( 'div', {
            className: 'labassistant-callout',
            text: '已写入草稿页：' + result.draft_commit_result.page_title
          } ) );
        }
        if ( result.editor_fill_notice ) {
          card.appendChild( createEl( 'div', {
            className: 'labassistant-callout',
            text: result.editor_fill_notice
          } ) );
        }
      }

      if ( result.write_preview ) {
        card.appendChild( createEl( 'h4', { text: result.write_preview.target_page || '整理结果' } ) );
        card.appendChild( createEl( 'div', {
          className: 'labassistant-status-note',
          text: [ result.write_preview.action_type, result.write_preview.operation ].filter( Boolean ).join( ' · ' )
        } ) );
        card.appendChild( createEl( 'div', {
          className: 'labassistant-markdown',
          html: renderMarkdown( result.write_preview.preview_text || '' )
        } ) );
        if ( editorMode === 'visual_editor' ) {
          var handoffWriteButton = createEl( 'button', {
            type: 'button',
            className: 'labassistant-inline-button',
            text: '切到源码编辑并填入草稿'
          } );
          handoffWriteButton.addEventListener( 'click', function () {
            navigateToSourceEdit( config, result.write_preview.preview_text || '', result );
          } );
          card.appendChild( handoffWriteButton );
        }
        if ( editorTextarea ) {
          var fillWriteButton = createEl( 'button', {
            type: 'button',
            className: 'labassistant-inline-button labassistant-inline-button-secondary',
            text: '填入编辑框'
          } );
          fillWriteButton.addEventListener( 'click', function () {
            fillEditorWithText( result, result.write_preview.preview_text || '', rerender );
          } );
          card.appendChild( fillWriteButton );
        }
        if ( result.write_preview.missing_fields && result.write_preview.missing_fields.length ) {
          card.appendChild( createEl( 'div', {
            className: 'labassistant-callout',
            text: '仍缺字段：' + result.write_preview.missing_fields.join( '、' )
          } ) );
        }
        if ( result.write_result ) {
          card.appendChild( createEl( 'div', {
            className: 'labassistant-callout',
            text: ( result.write_result.detail || '白名单直写已执行。' ) + ' 页面：' + ( result.write_result.page_title || '' )
          } ) );
        } else if ( result.write_preview.preview_id && !( result.write_preview.missing_fields && result.write_preview.missing_fields.length ) ) {
          var commitWriteButton = createEl( 'button', {
            type: 'button',
            className: 'labassistant-inline-button',
            text: '确认提交'
          } );
          commitWriteButton.addEventListener( 'click', function () {
            commitWriteButton.disabled = true;
            fetch( apiBase + '/write/commit', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'same-origin',
              body: JSON.stringify( {
                preview_id: result.write_preview.preview_id
              } )
            } ).then( function ( response ) {
              return response.json().then( function ( body ) {
                if ( !response.ok ) {
                  throw new Error( body.detail || '写入失败' );
                }
                result.write_result = body;
                rerender();
              } );
            } ).catch( function ( error ) {
              alert( error.message || '写入失败' );
            } ).finally( function () {
              commitWriteButton.disabled = false;
            } );
          } );
          card.appendChild( commitWriteButton );
        }
        if ( result.editor_fill_notice ) {
          card.appendChild( createEl( 'div', {
            className: 'labassistant-callout',
            text: result.editor_fill_notice
          } ) );
        }
      }

      var pageFormCard = renderPageFormFillCard( result, rerender );
      if ( pageFormCard ) {
        card.appendChild( pageFormCard );
      }
      var veCard = renderVisualEditorHandoffCard( result, rerender );
      if ( veCard ) {
        card.appendChild( veCard );
      }

      return card;
    }

    function buildStarterActions() {
      var pageFormContext = getPageFormRuntimeContext();
      var contextTitle = resolveEffectiveContextTitle( contextInput.value, config ) || '当前页';
      var isShotPage = /^Shot:/i.test( contextTitle );
      var formName = pageFormContext.resolvedFormName || '当前表单';
      var pageFormPrompts = {
        '术语条目': [
          '请根据当前页面整理一版术语条目字段建议；未知字段留空，不要写待补充或未知，最后单独列缺失字段。',
          '请把当前页面压缩成适合术语条目的字段建议；只填能确认的字段，其余留空并列缺失字段。',
          '请先指出术语条目仍缺哪些关键信息，再给出可填入字段；未知字段留空。'
        ],
        '设备条目': [
          '请根据当前页面整理一版设备条目字段建议；未知字段留空，不要写待补充或未知，最后单独列缺失字段。',
          '请把当前页面提炼成设备名称、系统归属、关键参数、用途、运行页和来源；只填能确认的字段。',
          '请先指出设备条目仍缺哪些关键信息，再给出可填入字段；未知字段留空。'
        ],
        '诊断条目': [
          '请根据当前页面整理一版诊断条目字段建议；未知字段留空，不要写待补充或未知，最后单独列缺失字段。',
          '请把当前页面提炼成诊断名称、测量对象、主要输出、易错点、工具入口和来源；只填能确认的字段。',
          '请先指出诊断条目仍缺哪些关键信息，再给出可填入字段；未知字段留空。'
        ],
        '文献导读': [
          '请根据当前页面整理一版文献导读字段建议；未知字段留空，不要写待补充、未知、无或表单上下文，最后单独列缺失字段。',
          '请把当前页面提炼成标题、作者、年份、DOI、摘要、相关页面和来源；只填能确认的字段，其余留空。',
          '请先指出文献导读仍缺哪些关键信息，再给出可填入字段；未知字段留空。'
        ],
        'Shot记录': [
          '请根据我上传的结果截图和说明，生成一版可直接回填的 Shot 记录字段建议、正文草稿和待确认项，并尽量补出处理结果文件与原始数据主目录。',
          '请结合当前 Shot 页面和附件结果图，整理出 Shot 记录字段建议；无法确认的字段放到待确认项。',
          '请先识别这次 Shot 的关键参数和主要观测，再生成一版可回填的记录草稿。'
        ]
      };
      var prompts = pageFormContext.editorMode === 'pageforms_edit' ? ( pageFormPrompts[ formName ] || [
        '请根据当前表单生成结构化字段建议，只输出字段名和值。',
        '请把当前页面整理成适合当前表单的字段建议。',
        '请先列出当前表单仍缺哪些关键字段，再给出可填入建议。'
      ] ) : editorMode === 'visual_editor' ? [
        '请把当前页面整理成可发布的页面草稿，我稍后会切到源码编辑填入。',
        '请把当前页面改写成新人可读的知识页草稿，并保留标题结构。',
        '请先给出一版可直接填入源码编辑器的草稿。'
      ] : isShotPage ? [
        '把当前页面整理成 shot 记录草稿',
        '把当前页面整理成周实验日志条目',
        '提炼当前页面的复盘摘要和待补字段'
      ] : editorTextarea ? [
        '请把当前页面整理成可直接填入编辑框的页面草稿，并保留 wiki 标题结构',
        '请把当前页面改写成新人可读版本，适合直接覆盖编辑框',
        '请补出当前页面仍缺的结构，并生成一版可编辑草稿'
      ] : [
        '把当前页面整理成术语条目草案',
        '把当前页面整理成新人可读的知识页草稿',
        '提炼当前页面的重点和仍缺信息'
      ];
      var actions = createEl( 'div', { className: 'labassistant-empty-actions' } );
      prompts.forEach( function ( text ) {
        var button = createEl( 'button', {
          type: 'button',
          className: 'labassistant-followup-button',
          text: text
        } );
        button.addEventListener( 'click', function () {
          questionInput.value = text;
          resizeQuestionInput();
          refreshComposerState();
          questionInput.focus();
        } );
        actions.appendChild( button );
      } );
      return actions;
    }

    function buildInspectorSections( result, isPending ) {
      var sections = [];

      if ( result.sources && result.sources.length ) {
        sections.push( {
          id: 'evidence',
          label: '证据',
          count: result.sources.length,
          render: function () {
            return renderSources( result );
          }
        } );
      }
      if ( result.step_stream && result.step_stream.length && ( variant === 'special' || isPending || ( result.unresolved_gaps && result.unresolved_gaps.length ) ) ) {
        sections.push( {
          id: 'process',
          label: '过程',
          count: result.step_stream.length,
          render: function () {
            return renderSteps( result );
          }
        } );
      }
      if ( variant === 'special' && result.action_trace && result.action_trace.length ) {
        sections.push( {
          id: 'action',
          label: '动作',
          count: result.action_trace.length,
          render: function () {
            return renderActions( result );
          }
        } );
      }
      if ( result.draft_preview || result.write_preview || result.write_result ) {
        sections.push( {
          id: 'write',
          label: compactWorkspace ? '草稿' : '写入',
          count: result.write_result ? 1 : 0,
          render: function () {
            return renderCommitCard( result, function () {
              scheduleTranscriptRender( true );
            } );
          }
        } );
      }

      if ( !sections.length ) {
        return null;
      }

      if ( isPending && sections.some( function ( section ) {
        return section.id === 'process';
      } ) ) {
        return {
          sections: sections,
          defaultSectionId: 'process'
        };
      }

      if ( sections.some( function ( section ) {
        return section.id === 'evidence';
      } ) ) {
        return {
          sections: sections,
          defaultSectionId: 'evidence'
        };
      }

      return {
        sections: sections,
        defaultSectionId: sections[ 0 ].id
      };
    }

    function renderInspector( result, isPending ) {
      var spec = buildInspectorSections( result, isPending );
      if ( !spec ) {
        return null;
      }

      var inspector = createEl( 'section', { className: 'labassistant-inspector' } );
      var tablist = createEl( 'div', {
        className: 'labassistant-inspector-tabs',
        role: 'tablist',
        'aria-label': '消息详情'
      } );
      var panel = createEl( 'div', { className: 'labassistant-inspector-panel' } );
      var activeId = spec.defaultSectionId;

      function updatePanel() {
        clearNode( panel );
        spec.sections.forEach( function ( section ) {
          section.button.classList.toggle( 'is-active', section.id === activeId );
          section.button.setAttribute( 'aria-selected', section.id === activeId ? 'true' : 'false' );
          if ( section.id === activeId ) {
            panel.appendChild( section.render() );
          }
        } );
      }

      spec.sections.forEach( function ( section ) {
        var label = section.label + ( section.count ? ' ' + section.count : '' );
        var button = createEl( 'button', {
          type: 'button',
          className: 'labassistant-inspector-tab',
          role: 'tab',
          text: label
        } );
        button.addEventListener( 'click', function () {
          activeId = section.id;
          updatePanel();
        } );
        section.button = button;
        tablist.appendChild( button );
      } );

      inspector.appendChild( tablist );
      inspector.appendChild( panel );
      updatePanel();

      if ( compactWorkspace ) {
        var summaryText = spec.sections.map( function ( section ) {
          return section.label + ( section.count ? ' ' + section.count : '' );
        } ).join( ' · ' );
        var toggle = createEl( 'button', {
          type: 'button',
          className: 'labassistant-inspector-toggle',
          text: ( isPending ? '正在整理：' : '查看详情：' ) + summaryText
        } );
        var body = createEl( 'div', { className: 'labassistant-inspector-body' }, [
          tablist,
          panel
        ] );
        var isOpen = !!isPending;

        function updateVisibility() {
          toggle.setAttribute( 'aria-expanded', isOpen ? 'true' : 'false' );
          body.hidden = !isOpen;
          body.style.display = isOpen ? 'grid' : 'none';
          inspector.classList.toggle( 'is-collapsed', !isOpen );
        }

        toggle.addEventListener( 'click', function () {
          isOpen = !isOpen;
          updateVisibility();
        } );

        clearNode( inspector );
        inspector.appendChild( toggle );
        inspector.appendChild( body );
        updateVisibility();
      }

      return inspector;
    }

    function renderAssistantBubble( result, isPending ) {
      var bubble = createEl( 'article', { className: 'labassistant-message assistant' } );
      var pageFormContext = getPageFormRuntimeContext();
      var metaText = [];
      if ( !compactWorkspace && result.model_info && result.model_info.resolved_model ) {
        metaText.push( result.model_info.provider );
        metaText.push( result.model_info.resolved_model );
      }
      if ( isPending ) {
        metaText.push( compactWorkspace ? '正在整理' : '响应中' );
      }
      bubble.appendChild( createEl( 'div', { className: 'labassistant-message-meta', text: metaText.join( ' · ' ) || ( compactWorkspace ? '助手' : '知识助手' ) } ) );

      var answerHtml = result.answer ? renderMarkdown( result.answer ) : '<p class="labassistant-thinking">正在思考…</p>';
      bubble.appendChild( createEl( 'div', { className: 'labassistant-markdown', html: answerHtml } ) );

      var resultFillCard = renderResultFillCard( result, function () {
        scheduleTranscriptRender( true );
      } );
      if ( resultFillCard ) {
        bubble.appendChild( resultFillCard );
      }

      var pdfIngestCard = renderPdfIngestReviewCard( result, function () {
        scheduleTranscriptRender( true );
      } );
      if ( pdfIngestCard ) {
        bubble.appendChild( pdfIngestCard );
      }

      var pdfControlCard = renderPdfControlPreviewCard( result, function () {
        scheduleTranscriptRender( true );
      } );
      if ( pdfControlCard ) {
        bubble.appendChild( pdfControlCard );
      }

      if ( editorTextarea && !isPending && result.answer && !( result.draft_preview || result.write_preview || result.pdf_ingest_review ) ) {
        var fillAnswerButton = createEl( 'button', {
          type: 'button',
          className: 'labassistant-inline-button labassistant-inline-button-secondary',
          text: '把这版回答填入编辑框'
        } );
        fillAnswerButton.addEventListener( 'click', function () {
          fillEditorWithText( result, result.answer || '', function () {
            scheduleTranscriptRender( true );
          } );
        } );
        bubble.appendChild( fillAnswerButton );
      }

      if ( result.unresolved_gaps && result.unresolved_gaps.length ) {
        bubble.appendChild( createEl( 'div', {
          className: 'labassistant-callout',
          text: '待补证据：' + result.unresolved_gaps.join( '；' )
        } ) );
      }

      if ( result.editor_fill_notice ) {
        bubble.appendChild( createEl( 'div', {
          className: 'labassistant-callout',
          text: result.editor_fill_notice
        } ) );
      }

      if ( pageFormContext.editorMode === 'pageforms_edit' && !( result.draft_preview || result.write_preview ) ) {
        var formFillCard = renderPageFormFillCard( result, function () {
          scheduleTranscriptRender( true );
        } );
        if ( formFillCard ) {
          bubble.appendChild( formFillCard );
        }
      }

      if ( editorMode === 'visual_editor' && !( result.draft_preview || result.write_preview ) ) {
        var handoffCard = renderVisualEditorHandoffCard( result, function () {
          scheduleTranscriptRender( true );
        } );
        if ( handoffCard ) {
          bubble.appendChild( handoffCard );
        }
      }

      var inspector = renderInspector( result, isPending );
      if ( inspector ) {
        bubble.appendChild( inspector );
      }

      if ( result.suggested_followups && result.suggested_followups.length ) {
        var followups = createEl( 'div', { className: 'labassistant-followups' } );
        result.suggested_followups.forEach( function ( item ) {
          var button = createEl( 'button', {
            type: 'button',
            className: 'labassistant-followup-button',
            text: item
          } );
          button.addEventListener( 'click', function () {
            questionInput.value = item;
            resizeQuestionInput();
            refreshComposerState();
            questionInput.focus();
          } );
          followups.appendChild( button );
        } );
        bubble.appendChild( followups );
      }

      return bubble;
    }

    function scheduleTranscriptRender( immediate ) {
      if ( immediate ) {
        if ( state.renderTimer ) {
          clearTimeout( state.renderTimer );
          state.renderTimer = null;
        }
        renderTranscript();
        return;
      }
      if ( state.renderTimer ) {
        return;
      }
      state.renderTimer = window.setTimeout( function () {
        state.renderTimer = null;
        renderTranscript();
      }, 64 );
    }

    function renderTranscript() {
      clearNode( transcript );
      var items = buildTranscriptItems();
      if ( !items.length ) {
        var emptyState = createEl( 'div', { className: 'labassistant-empty-state' }, [
          createEl( 'strong', { text: editorMode === 'pageforms_edit' ? '先让助手生成一版可直接填入表单的字段建议。' : editorMode === 'visual_editor' ? '先让助手生成草稿，再切到源码编辑预填。' : editorTextarea ? '先让助手整理一版可直接填入编辑框的草稿。' : '先让助手帮你整理当前页。' } ),
          createEl( 'span', {
            text: editorMode === 'pageforms_edit' ?
              '它会先给出结构化字段建议，你确认后再填表；不会自动提交。' :
              editorMode === 'visual_editor' ?
              '它会先生成草稿，再由你切到源码编辑填入；不会直接修改可视化编辑器。' :
              editorTextarea ?
              '它会先基于当前页生成可编辑草稿，你确认后再自己保存页面。' :
              '它更适合把词条、shot、周实验日志和知识页先整理成草稿，再由你确认。'
          } ),
          buildStarterActions()
        ] );
        if ( state.sourceEditNotice ) {
          emptyState.appendChild( createEl( 'div', {
            className: 'labassistant-callout',
            text: state.sourceEditNotice
          } ) );
        }
        transcript.appendChild( emptyState );
        publishSubmissionGuidance();
        return;
      }

      items.forEach( function ( item ) {
        if ( item.role === 'user' ) {
          transcript.appendChild( createEl( 'article', { className: 'labassistant-message user' }, [
            createEl( 'div', { className: 'labassistant-message-meta', text: '你' } ),
            createEl( 'div', {
              className: 'labassistant-markdown',
              html: renderMarkdown( item.text )
            } )
          ] ) );
          return;
        }
        transcript.appendChild( renderAssistantBubble( item.result || {}, item.isPending ) );
      } );
      enhanceMarkdownContainers( transcript );
      scrollTranscriptToBottom();
      publishSubmissionGuidance();
    }

    function refreshComposerState() {
      sendButton.disabled = !questionInput.value.trim();
    }

    function buildPdfIngestQuestion( attachmentItem ) {
      var contextTitle = resolveEffectiveContextTitle( contextInput.value, config ) || config.currentTitle || '';
      var fileName = attachmentItem && attachmentItem.name ? String( attachmentItem.name ) : '当前 PDF';
      var prompt = '请分析 PDF《' + fileName + '》，总结内容并建议最适合写入的 wiki 区域；先返回摘要、推荐归档区域和章节整理，等待我确认后再生成草稿预览。';
      if ( contextTitle ) {
        prompt += ' 当前页面：' + contextTitle + '。';
      }
      return prompt;
    }

    function startStreamingRequest( payload, options ) {
      var requestOptions = options || {};
      if ( !payload || !payload.question ) {
        alert( '请输入问题。' );
        return;
      }

      if ( compactWorkspace ) {
        setDrawerPopoverOpen( false );
      }
      setUploadMenuOpen( false );

      state.pendingQuestion = payload.question;
      state.currentResult = {
        answer: '',
        sources: [],
        unresolved_gaps: [],
        suggested_followups: [],
        action_trace: [],
        step_stream: [ {
          title: '准备请求',
          stage: 'prepare',
          status: 'running',
          detail: '正在建立流式连接。'
        } ]
      };

      if ( Array.isArray( requestOptions.consumeAttachmentClientIds ) ) {
        state.attachments = state.attachments.filter( function ( entry ) {
          return requestOptions.consumeAttachmentClientIds.indexOf( entry.clientId ) === -1;
        } );
      } else if ( requestOptions.clearAttachments !== false ) {
        state.attachments = [];
      }

      if ( requestOptions.clearQuestion !== false ) {
        questionInput.value = '';
        resizeQuestionInput();
      }
      refreshComposerState();
      renderAttachments();
      renderTranscript();

      streamChat( apiBase, payload, function ( event ) {
        var body = event.data || {};
        if ( event.event === 'session_started' ) {
          state.sessionId = body.session_id || state.sessionId;
          state.historyLoaded = false;
          if ( body.model_info ) {
            syncSelectedModelFromInfo( body.model_info );
            refreshModelSelectors();
            refreshModelBadge( body.model_info );
          }
          if ( state.sessionId ) {
            localStorage.setItem( STORAGE_KEY, state.sessionId );
          }
          refreshSessionBadge();
          return;
        }
        if ( event.event === 'step' ) {
          state.currentResult.step_stream = upsertStep( state.currentResult.step_stream || [], body );
          scheduleTranscriptRender( true );
          return;
        }
        if ( event.event === 'token' ) {
          state.currentResult.answer = ( state.currentResult.answer || '' ) + ( body.delta || '' );
          scheduleTranscriptRender( false );
          return;
        }
        if ( event.event === 'sources' ) {
          state.currentResult.sources = body.sources || [];
          scheduleTranscriptRender( true );
          return;
        }
        if ( event.event === 'action_trace' ) {
          state.currentResult.action_trace = body.items || [];
          scheduleTranscriptRender( true );
          return;
        }
        if ( event.event === 'draft_preview' ) {
          state.currentResult.draft_preview = body;
          scheduleTranscriptRender( true );
          return;
        }
        if ( event.event === 'write_preview' ) {
          state.currentResult.write_preview = body;
          scheduleTranscriptRender( true );
          return;
        }
        if ( event.event === 'write_result' ) {
          state.currentResult.write_result = body;
          scheduleTranscriptRender( true );
          return;
        }
        if ( event.event === 'result_fill' ) {
          state.currentResult.result_fill = body;
          scheduleTranscriptRender( true );
          return;
        }
        if ( event.event === 'pdf_ingest_review' ) {
          state.currentResult.pdf_ingest_review = body;
          scheduleTranscriptRender( true );
          return;
        }
        if ( event.event === 'done' ) {
          applyDonePayload( body );
          return;
        }
        if ( event.event === 'error' ) {
          state.currentResult.answer = state.currentResult.answer || '当前请求没有完成。';
          state.currentResult.unresolved_gaps = [ body.detail || '未知错误' ];
          state.currentResult.step_stream = upsertStep( state.currentResult.step_stream || [], {
            stage: 'error',
            title: '助手循环中断',
            status: 'waiting',
            detail: body.detail || '未知错误'
          } );
          renderTranscript();
        }
      } ).catch( function ( error ) {
        state.currentResult.answer = state.currentResult.answer || '当前请求没有完成。';
        state.currentResult.unresolved_gaps = [ error.message || '未知错误' ];
        state.currentResult.step_stream = upsertStep( state.currentResult.step_stream || [], {
          stage: 'error',
          title: '助手循环中断',
          status: 'waiting',
          detail: error.message || '未知错误'
        } );
        renderTranscript();
      } ).finally( function () {
        sendButton.disabled = false;
      } );
    }

    function startPdfIngestForAttachment( attachmentItem ) {
      var selectedModel = findSelectedModelItem();
      var contextTitle = resolveEffectiveContextTitle( contextInput.value, config ) || '';
      if ( !attachmentItem || !attachmentItem.id || attachmentItem.status !== 'ready' ) {
        alert( '请等待 PDF 附件上传完成后再分析。' );
        return;
      }
      startStreamingRequest( {
        question: buildPdfIngestQuestion( attachmentItem ),
        mode: 'qa',
        detail_level: detailSelect.value,
        context_pages: contextTitle ? [ contextTitle ] : [],
        attachments: [ {
          id: attachmentItem.id,
          kind: attachmentItem.kind,
          name: attachmentItem.name,
          mime_type: attachmentItem.mime_type,
          size_bytes: attachmentItem.size_bytes
        } ],
        workflow_hint: 'pdf_ingest_write',
        user_name: config.userName || null,
        session_id: state.sessionId || undefined,
        generation_model: state.selectedModel || undefined,
        generation_provider: selectedModel ? selectedModel.provider : undefined
      }, {
        consumeAttachmentClientIds: [ attachmentItem.clientId ]
      } );
    }

    function applyDonePayload( body ) {
      state.currentResult = body;
      if ( body.model_info ) {
        syncSelectedModelFromInfo( body.model_info );
        refreshModelSelectors();
        refreshModelBadge( body.model_info );
      }
      appendTurnFromResponse( body );
      renderTranscript();
    }

    function submitQuestion() {
      if ( state.attachments.some( function ( item ) { return item.status === 'uploading'; } ) ) {
        alert( '附件仍在上传中，请稍等完成后再发送。' );
        return;
      }
      var readyAttachments = state.attachments.filter( function ( item ) {
        return item.status === 'ready' && item.id;
      } ).map( function ( item ) {
        return {
          id: item.id,
          kind: item.kind,
          name: item.name,
          mime_type: item.mime_type,
          size_bytes: item.size_bytes
        };
      } );
      var payload = {
        question: questionInput.value.trim(),
        mode: 'qa',
        detail_level: detailSelect.value,
        context_pages: resolveEffectiveContextTitle( contextInput.value, config ) ? [ resolveEffectiveContextTitle( contextInput.value, config ) ] : [],
        attachments: readyAttachments,
        user_name: config.userName || null
      };
      payload.workflow_hint = inferWorkflowHint(
        payload.question,
        payload.context_pages[ 0 ] || resolveEffectiveContextTitle( contextInput.value, config ) || '',
        readyAttachments
      );
      if ( state.selectedModel ) {
        payload.generation_model = state.selectedModel;
      }
      if ( findSelectedModelItem() ) {
        payload.generation_provider = findSelectedModelItem().provider;
      }
      if ( state.sessionId ) {
        payload.session_id = state.sessionId;
      }
      if ( !payload.question ) {
        alert( '请输入问题。' );
        return;
      }
      startStreamingRequest( payload, { clearAttachments: true } );
    }

    function resetConversation() {
      state.sessionId = null;
      state.turns = [];
      state.pendingQuestion = '';
      state.currentResult = null;
      if ( state.renderTimer ) {
        clearTimeout( state.renderTimer );
        state.renderTimer = null;
      }
      state.drawerPopoverOpen = false;
      state.historyOpen = false;
      state.historyLoaded = false;
      state.historySessions = [];
      state.historyQuery = '';
      state.historyError = '';
      state.historyNotice = '';
      state.uploadMenuOpen = false;
      state.attachments = [];
      questionInput.value = '';
      resizeQuestionInput();
      refreshComposerState();
      clearAssistantLocalState();
      localStorage.setItem( HOST_STORAGE_KEY, window.location.host );
      refreshSessionBadge();
      refreshContextBadge();
      refreshModelBadge();
      refreshLayoutState();
      renderAttachments();
      renderTranscript();
    }

    questionInput.addEventListener( 'keydown', function ( event ) {
      if ( event.key === 'Enter' && !event.shiftKey ) {
        event.preventDefault();
        submitQuestion();
      }
    } );
    questionInput.addEventListener( 'input', function () {
      resizeQuestionInput();
      refreshComposerState();
    } );
    sendButton.addEventListener( 'click', submitQuestion );
    resetButton.addEventListener( 'click', resetConversation );
    historyButton.addEventListener( 'click', function () {
      setHistoryOpen( !state.historyOpen );
    } );
    settingsButton.addEventListener( 'click', function () {
      if ( compactWorkspace ) {
        setDrawerPopoverOpen( !state.drawerPopoverOpen );
        return;
      }
      state.showSettings = !state.showSettings;
      refreshLayoutState();
    } );
    historySearchInput.addEventListener( 'input', function () {
      state.historyQuery = historySearchInput.value || '';
      renderHistoryPanel();
    } );
    plusButton.addEventListener( 'click', function () {
      setUploadMenuOpen( !state.uploadMenuOpen );
    } );
    uploadImageButton.addEventListener( 'click', function () {
      imageUploadInput.click();
    } );
    uploadDocumentButton.addEventListener( 'click', function () {
      documentUploadInput.click();
    } );
    imageUploadInput.addEventListener( 'change', function () {
      handleFilesSelected( imageUploadInput.files );
      imageUploadInput.value = '';
      setUploadMenuOpen( false );
    } );
    documentUploadInput.addEventListener( 'change', function () {
      handleFilesSelected( documentUploadInput.files );
      documentUploadInput.value = '';
      setUploadMenuOpen( false );
    } );
    questionInput.addEventListener( 'paste', function ( event ) {
      var utils = getAttachmentUtils();
      var pastedFiles;
      if ( !utils || !utils.extractClipboardFiles || !event.clipboardData || !event.clipboardData.items ) {
        return;
      }
      pastedFiles = utils.extractClipboardFiles( event.clipboardData.items );
      if ( !pastedFiles.length ) {
        return;
      }
      event.preventDefault();
      handleFilesSelected( pastedFiles );
      setUploadMenuOpen( false );
    } );
    contextInput.addEventListener( 'input', refreshContextBadge );
    familySelect.addEventListener( 'change', function () {
      state.selectedFamily = familySelect.value;
      state.selectedModel = null;
      refreshModelSelectors();
      maybePatchSessionModel();
    } );
    modelSelect.addEventListener( 'change', function () {
      state.selectedModel = modelSelect.value;
      persistModelSelection();
      refreshModelBadge();
      maybePatchSessionModel();
    } );
    compactModelSelect.addEventListener( 'change', function () {
      state.selectedModel = compactModelSelect.value;
      state.selectedFamily = inferFamily( state.selectedModel );
      persistModelSelection();
      refreshModelSelectors();
      maybePatchSessionModel();
    } );
    showAllToggle.addEventListener( 'change', function () {
      state.showAllModels = showAllToggle.checked;
      loadModelCatalog( apiBase, state.showAllModels ).then( function ( body ) {
        state.modelCatalog = body;
        refreshModelSelectors();
      } ).catch( function ( error ) {
        console.warn( error );
        modelBadge.textContent = '模型：目录读取失败';
      } );
    } );
    if ( closeButton ) {
      closeButton.addEventListener( 'click', function () {
        options.onClose();
      } );
    }
    document.addEventListener( 'click', function ( event ) {
      if ( drawerSettingsPopover && state.drawerPopoverOpen ) {
        if ( drawerSettingsPopover.contains( event.target ) || settingsButton.contains( event.target ) ) {
          return;
        }
        setDrawerPopoverOpen( false );
      }
      if ( state.uploadMenuOpen ) {
        if ( uploadMenu.contains( event.target ) || plusButton.contains( event.target ) ) {
          return;
        }
        setUploadMenuOpen( false );
      }
    } );
    document.addEventListener( 'keydown', function ( event ) {
      if ( event.key === 'Escape' ) {
        if ( state.drawerPopoverOpen ) {
          setDrawerPopoverOpen( false );
        }
        if ( state.uploadMenuOpen ) {
          setUploadMenuOpen( false );
        }
      }
    } );

    var mainColumn = createEl( 'div', { className: 'labassistant-main-column' }, [
      header,
      controlStack,
      transcript,
      composer
    ] );

    if ( variant === 'special' ) {
      var infoPanel = createEl( 'aside', { className: 'labassistant-special-aside' }, [
        createEl( 'section', { className: 'labassistant-aside-card' }, [
          createEl( 'small', { text: 'Workspace' } ),
          createEl( 'h3', { text: '高级工作台' } ),
          createEl( 'p', { text: '这里保留完整会话、模型选择和当前页面上下文设置，适合重度使用和调试。' } )
        ] ),
        createEl( 'section', { className: 'labassistant-aside-card' }, [
          createEl( 'small', { text: 'Context' } ),
          createEl( 'h3', { text: '当前页面' } ),
          createEl( 'p', { text: config.currentTitle || '无' } )
        ] )
      ] );
      root.appendChild( createEl( 'div', { className: 'labassistant-special-layout' }, [
        mainColumn,
        infoPanel
      ] ) );
    } else {
      root.appendChild( mainColumn );
    }

    refreshLayoutState();
    renderHistoryPanel();
    refreshSessionBadge();
    refreshContextBadge();
    renderAttachments();
    renderTranscript();
    resizeQuestionInput();
    refreshComposerState();

    if ( consumedDraftHandoff && consumedDraftHandoff.content ) {
      if ( fillEditorWithText( null, consumedDraftHandoff.content, null ) ) {
        state.sourceEditNotice = '已从可视化编辑页带入草稿，页面尚未保存。';
        renderTranscript();
      }
    }

    loadModelCatalog( apiBase, false ).then( function ( body ) {
      state.modelCatalog = body;
      if ( !state.selectedModel ) {
        state.selectedModel = body.default_model;
      }
      if ( !state.selectedFamily ) {
        state.selectedFamily = inferFamily( state.selectedModel || body.default_model );
      }
      refreshModelSelectors();
    } ).catch( function ( error ) {
      console.warn( error );
      modelBadge.textContent = '模型：目录读取失败';
    } );

    if ( state.sessionId ) {
      loadSession( apiBase, state.sessionId ).then( function ( body ) {
        state.turns = body.turns || [];
        if ( body.model_info ) {
          syncSelectedModelFromInfo( body.model_info );
          refreshModelSelectors();
          refreshModelBadge( body.model_info );
        }
        renderTranscript();
      } ).catch( function () {
        state.sessionId = null;
        clearAssistantLocalState();
        localStorage.setItem( HOST_STORAGE_KEY, window.location.host );
        refreshSessionBadge();
      } );
    }

    return {
      root: root,
      setQuestion: function ( text ) {
        questionInput.value = text || '';
        resizeQuestionInput();
        refreshComposerState();
        questionInput.focus();
      }
    };
  }

  function createPluginShell( config ) {
    if ( !syncHostScopedState() ) {
      return null;
    }
    syncModelPreferenceVersion();
    var shellUtils = getShellUtils();

    var root = document.getElementById( DRAWER_ROOT_ID );
    if ( root ) {
      return root.__labassistantController;
    }

    var isOpen = false;
    var shellState = shellUtils && shellUtils.resolveShellPresentation ?
      shellUtils.resolveShellPresentation( window.innerWidth ) :
      { shellVariant: 'plugin', showBackdrop: false, lockBodyScroll: false };
    var backdrop = createEl( 'div', { className: 'labassistant-plugin-backdrop', hidden: 'hidden' } );
    var container = createEl( 'div', {
      id: DRAWER_ROOT_ID,
      className: 'labassistant-plugin-shell',
      hidden: 'hidden'
    } );

    function applyShellPresentation() {
      shellState = shellUtils && shellUtils.resolveShellPresentation ?
        shellUtils.resolveShellPresentation( window.innerWidth ) :
        { shellVariant: 'plugin', showBackdrop: false, lockBodyScroll: false };
      container.classList.toggle( 'is-plugin', shellState.shellVariant === 'plugin' );
      container.classList.toggle( 'is-mobile-sheet', shellState.shellVariant === 'mobile-sheet' );
      backdrop.classList.toggle( 'is-active', !!( isOpen && shellState.showBackdrop ) );
      backdrop.hidden = !( isOpen && shellState.showBackdrop );
      container.hidden = !isOpen;
      document.body.classList.toggle(
        'labassistant-mobile-sheet-open',
        !!( isOpen && shellState.lockBodyScroll )
      );
    }

    function close() {
      isOpen = false;
      applyShellPresentation();
    }

    function open() {
      isOpen = true;
      applyShellPresentation();
    }

    function toggle() {
      isOpen = !isOpen;
      applyShellPresentation();
    }

    backdrop.addEventListener( 'click', close );
    document.addEventListener( 'keydown', function ( event ) {
      if ( event.key === 'Escape' && !container.hidden ) {
        close();
      }
    } );
    window.addEventListener( 'resize', applyShellPresentation );

    var workspace = createWorkspace( config, {
      variant: 'plugin',
      onClose: close,
      closeLabel: '最小化'
    } );
    container.appendChild( workspace.root );
    document.body.appendChild( backdrop );
    document.body.appendChild( container );
    applyShellPresentation();

    var controller = {
      open: open,
      close: close,
      toggle: toggle,
      minimize: close,
      setQuestion: function ( text ) {
        workspace.setQuestion( text );
      }
    };
    container.__labassistantController = controller;
    return controller;
  }

  function mountSpecial( root, config ) {
    if ( !syncHostScopedState() ) {
      return;
    }
    syncModelPreferenceVersion();
    if ( root.dataset.labassistantMounted === 'true' ) {
      return;
    }
    clearNode( root );
    var workspace = createWorkspace( config, { variant: 'special' } );
    root.appendChild( workspace.root );
    root.dataset.labassistantMounted = 'true';
  }

  mw.labassistantUI = {
    mountDrawer: function ( container, config ) {
      var controller = createPluginShell( config );
      if ( !controller ) {
        return {
          open: function () {},
          close: function () {},
          toggle: function () {},
          minimize: function () {}
        };
      }
      return controller;
    },
    mountSpecial: mountSpecial
  };
}() );
