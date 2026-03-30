( function () {
  function inferModelFamily( model, fallbackFamily ) {
    var normalized = String( model || '' ).trim();
    if ( !normalized ) {
      return fallbackFamily || 'gpt';
    }
    if ( normalized.indexOf( 'claude-' ) === 0 ) {
      return 'claude';
    }
    if ( normalized.indexOf( 'gemini-' ) === 0 ) {
      return 'gemini';
    }
    return 'gpt';
  }

  var exported = {
    inferModelFamily: inferModelFamily
  };

  if ( typeof window !== 'undefined' ) {
    window.LabAssistantModelUtils = exported;
  }
  if ( typeof mw !== 'undefined' ) {
    mw.labassistantModelUtils = exported;
  }
  if ( typeof module !== 'undefined' && module.exports ) {
    module.exports = exported;
  }
}() );
