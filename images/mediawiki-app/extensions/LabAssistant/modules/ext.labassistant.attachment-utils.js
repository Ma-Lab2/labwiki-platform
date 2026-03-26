( function () {
  function isRelativeApiBase( value ) {
    return typeof value === 'string' && value.indexOf( '/' ) === 0 && !/^[a-z]+:\/\//i.test( value );
  }

  function resolveApiBase( apiBase, locationLike ) {
    var base = apiBase || '/tools/assistant/api';
    var protocol = ( locationLike && locationLike.protocol ) || 'http:';
    var hostname = ( locationLike && locationLike.hostname ) || '';
    var port = ( locationLike && locationLike.port ) || '';
    var loopbackHost = hostname === '127.0.0.1';

    if ( !loopbackHost || !isRelativeApiBase( base ) ) {
      return base;
    }

    return protocol + '//localhost' + ( port ? ':' + port : '' ) + base;
  }

  function extractClipboardFiles( items ) {
    return Array.from( items || [] ).map( function ( item ) {
      if ( !item || item.kind !== 'file' || typeof item.getAsFile !== 'function' ) {
        return null;
      }
      return item.getAsFile();
    } ).filter( function ( file ) {
      return !!file;
    } );
  }

  function buildAttachmentContentUrl( apiBase, attachmentId, locationLike ) {
    var base = resolveApiBase( apiBase, locationLike );
    var normalizedBase = String( base || '/tools/assistant/api' ).replace( /\/+$/, '' );
    return normalizedBase + '/attachments/' + encodeURIComponent( String( attachmentId || '' ) ) + '/content';
  }

  var exported = {
    buildAttachmentContentUrl: buildAttachmentContentUrl,
    extractClipboardFiles: extractClipboardFiles,
    resolveApiBase: resolveApiBase
  };

  if ( typeof window !== 'undefined' ) {
    window.LabAssistantAttachmentUtils = exported;
  }
  if ( typeof mw !== 'undefined' ) {
    mw.labassistantAttachmentUtils = exported;
  }
  if ( typeof module !== 'undefined' && module.exports ) {
    module.exports = exported;
  }
}() );
