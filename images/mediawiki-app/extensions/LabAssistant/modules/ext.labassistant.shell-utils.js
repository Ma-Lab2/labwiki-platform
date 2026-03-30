( function () {
  var DEFAULT_MOBILE_BREAKPOINT = 720;

  function resolveShellPresentation( viewportWidth, mobileBreakpoint ) {
    var breakpoint = typeof mobileBreakpoint === 'number' ? mobileBreakpoint : DEFAULT_MOBILE_BREAKPOINT;
    var width = typeof viewportWidth === 'number' && !Number.isNaN( viewportWidth ) ? viewportWidth : breakpoint + 1;
    var isMobile = width <= breakpoint;

    return {
      shellVariant: isMobile ? 'mobile-sheet' : 'plugin',
      showBackdrop: isMobile,
      lockBodyScroll: isMobile,
      pointerMode: isMobile ? 'modal' : 'passthrough'
    };
  }

  function isCompactWorkspaceVariant( variant ) {
    return variant === 'drawer' || variant === 'plugin' || variant === 'mobile-sheet';
  }

  function shouldHydrateStoredSession( variant ) {
    return variant !== 'special';
  }

  var exported = {
    DEFAULT_MOBILE_BREAKPOINT: DEFAULT_MOBILE_BREAKPOINT,
    isCompactWorkspaceVariant: isCompactWorkspaceVariant,
    resolveShellPresentation: resolveShellPresentation,
    shouldHydrateStoredSession: shouldHydrateStoredSession
  };

  if ( typeof window !== 'undefined' ) {
    window.LabAssistantShellUtils = exported;
  }
  if ( typeof mw !== 'undefined' ) {
    mw.labassistantShellUtils = exported;
  }
  if ( typeof module !== 'undefined' && module.exports ) {
    module.exports = exported;
  }
}() );
