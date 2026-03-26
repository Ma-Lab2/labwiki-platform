( function () {
  function normalizeString( value ) {
    return String( value || '' ).trim();
  }

  function normalizeBlockedItems( items ) {
    return ( Array.isArray( items ) ? items : [] ).map( function ( item ) {
      return {
        label: normalizeString( item && item.label ) || '未命名章节',
        reason: normalizeString( item && item.reason ) || '包含受限信息，应转到受限页人工维护。',
        content: normalizeString( item && item.content )
      };
    } ).filter( function ( item ) {
      return !!item.content;
    } );
  }

  function normalizePdfControlPreview( payload ) {
    var item = payload || {};
    var previewId = normalizeString( item.preview_id );
    var targetPage = normalizeString( item.target_page );
    if ( !previewId || !targetPage ) {
      return null;
    }
    return {
      preview_id: previewId,
      target_page: targetPage,
      overview_page: normalizeString( item.overview_page ) || 'Control:控制与运行总览',
      content: normalizeString( item.content ),
      overview_update: normalizeString( item.overview_update ),
      blocked_items: normalizeBlockedItems( item.blocked_items ),
      metadata: item.metadata && typeof item.metadata === 'object' ? item.metadata : null
    };
  }

  var exported = {
    normalizeBlockedItems: normalizeBlockedItems,
    normalizePdfControlPreview: normalizePdfControlPreview
  };

  if ( typeof module !== 'undefined' && module.exports ) {
    module.exports = exported;
  }

  if ( typeof window !== 'undefined' ) {
    window.LabAssistantPdfIngestUtils = exported;
    if ( window.mw ) {
      window.mw.labassistantPdfIngestUtils = exported;
    }
  }
}() );
