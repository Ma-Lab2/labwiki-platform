( function () {
  var ASSET_VERSION = '2026-03-26-pdf-control-formalize-1';

  if ( typeof window !== 'undefined' ) {
    window.LabAssistantAssetVersion = ASSET_VERSION;
  }

  if ( typeof mw !== 'undefined' ) {
    mw.labassistantAssetVersion = ASSET_VERSION;
  }

  if ( typeof module !== 'undefined' && module.exports ) {
    module.exports = {
      assetVersion: ASSET_VERSION
    };
  }
}() );
