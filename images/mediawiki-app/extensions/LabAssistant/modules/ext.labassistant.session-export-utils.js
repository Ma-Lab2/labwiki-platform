( function () {
  function safeText( value ) {
    return String( value || '' ).trim();
  }

  function normalizeSessionHistoryItems( payload ) {
    var items = Array.isArray( payload ) ? payload : ( payload && Array.isArray( payload.sessions ) ? payload.sessions : [] );
    return items.map( function ( item ) {
      var normalized = {
        session_id: safeText( item && item.session_id ),
        current_page: safeText( item && item.current_page ),
        latest_question: safeText( item && item.latest_question ),
        turn_count: Number( item && item.turn_count ) || 0
      };
      if ( item && item.created_at ) {
        normalized.created_at = item.created_at;
      }
      if ( item && item.updated_at ) {
        normalized.updated_at = item.updated_at;
      }
      if ( safeText( item && item.user_name ) ) {
        normalized.user_name = safeText( item && item.user_name );
      }
      return normalized;
    } ).filter( function ( item ) {
      return !!item.session_id;
    } );
  }

  function filterSessionHistoryItems( items, query ) {
    var normalizedQuery = safeText( query ).toLowerCase();
    if ( !normalizedQuery ) {
      return ( items || [] ).slice();
    }
    return ( items || [] ).filter( function ( item ) {
      return [
        item.session_id,
        item.current_page,
        item.latest_question
      ].some( function ( value ) {
        return safeText( value ).toLowerCase().indexOf( normalizedQuery ) !== -1;
      } );
    } );
  }

  function sanitizeFileStem( value ) {
    var stem = safeText( value ).replace( /[^0-9A-Za-z._-]+/g, '-' ).replace( /-+/g, '-' ).replace( /^-+|-+$/g, '' );
    return stem || 'labassistant-session';
  }

  function buildSessionExportFileName( item ) {
    var sessionId = safeText( item && item.session_id ) || 'session';
    var shortId = sessionId.slice( 0, 8 );
    var page = safeText( item && item.current_page );
    if ( page ) {
      return sanitizeFileStem( page ) + '-session-' + shortId + '.md';
    }
    return 'labassistant-session-' + shortId + '.md';
  }

  var exported = {
    normalizeSessionHistoryItems: normalizeSessionHistoryItems,
    filterSessionHistoryItems: filterSessionHistoryItems,
    buildSessionExportFileName: buildSessionExportFileName
  };

  if ( typeof module !== 'undefined' && module.exports ) {
    module.exports = exported;
  }

  if ( typeof window !== 'undefined' ) {
    window.LabAssistantSessionExportUtils = exported;
    if ( window.mw ) {
      window.mw.labassistantSessionExportUtils = exported;
    }
  }
}() );
