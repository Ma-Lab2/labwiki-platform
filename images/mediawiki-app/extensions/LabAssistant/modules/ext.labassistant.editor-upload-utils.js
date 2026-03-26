( function () {
  var MIME_EXTENSION_MAP = {
    'image/png': 'png',
    'image/jpeg': 'jpg',
    'image/webp': 'webp'
  };

  function padNumber( value ) {
    return String( value ).padStart( 2, '0' );
  }

  function sanitizeTitleStem( value ) {
    return String( value || 'clipboard-image' )
      .replace( /[:/\\]+/g, '-' )
      .replace( /[^A-Za-z0-9._\-\u4e00-\u9fff]+/g, '-' )
      .replace( /-+/g, '-' )
      .replace( /^-+|-+$/g, '' ) || 'clipboard-image';
  }

  function buildTimestamp( value ) {
    return value.getUTCFullYear() +
      padNumber( value.getUTCMonth() + 1 ) +
      padNumber( value.getUTCDate() ) + '-' +
      padNumber( value.getUTCHours() ) +
      padNumber( value.getUTCMinutes() ) +
      padNumber( value.getUTCSeconds() );
  }

  function buildClipboardUploadFilename( pageTitle, mimeType, now ) {
    var stamp = buildTimestamp( now instanceof Date ? now : new Date() );
    var extension = MIME_EXTENSION_MAP[ mimeType ] || 'png';
    return sanitizeTitleStem( pageTitle ) + '-' + stamp + '.' + extension;
  }

  function buildWikiImageMarkup( fileName ) {
    return '\n[[File:' + String( fileName || '' ) + '|thumb]]\n';
  }

  function insertTextAtCursor( textarea, text ) {
    var start = textarea.selectionStart || 0;
    var end = textarea.selectionEnd || 0;
    var value = textarea.value || '';
    var inserted = String( text || '' );

    textarea.value = value.slice( 0, start ) + inserted + value.slice( end );
    textarea.selectionStart = start + inserted.length;
    textarea.selectionEnd = textarea.selectionStart;
    if ( typeof textarea.focus === 'function' ) {
      textarea.focus();
    }
    if ( typeof textarea.dispatchEvent === 'function' ) {
      textarea.dispatchEvent( new Event( 'input', { bubbles: true } ) );
      textarea.dispatchEvent( new Event( 'change', { bubbles: true } ) );
    }
  }

  function isSupportedWikiImageFile( file ) {
    return !!( file && MIME_EXTENSION_MAP[ file.type ] );
  }

  var exported = {
    buildClipboardUploadFilename: buildClipboardUploadFilename,
    buildWikiImageMarkup: buildWikiImageMarkup,
    insertTextAtCursor: insertTextAtCursor,
    isSupportedWikiImageFile: isSupportedWikiImageFile
  };

  if ( typeof window !== 'undefined' ) {
    window.LabAssistantEditorUploadUtils = exported;
  }
  if ( typeof mw !== 'undefined' ) {
    mw.labassistantEditorUploadUtils = exported;
  }
  if ( typeof module !== 'undefined' && module.exports ) {
    module.exports = exported;
  }
}() );
