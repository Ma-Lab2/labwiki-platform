( function () {
  function normalizeString( value ) {
    return String( value || '' ).trim();
  }

  function isLiteratureGuideTitle( value ) {
    return /^文献导读\//.test( normalizeString( value ) );
  }

  function stripWikiFilePrefix( value ) {
    return normalizeString( value ).replace( /^(?:File|文件|Media|媒体):/i, '' );
  }

  function buildWikiFileRedirectUrl( fileTitle, mwLike ) {
    var normalizedTitle = normalizeString( fileTitle );
    var bareFileName = stripWikiFilePrefix( normalizedTitle );
    if ( !bareFileName ) {
      return '';
    }
    if ( mwLike && mwLike.util && typeof mwLike.util.getUrl === 'function' ) {
      return mwLike.util.getUrl( 'Special:Redirect/file/' + bareFileName );
    }
    return '/wiki/Special:Redirect/file/' + encodeURIComponent( bareFileName ).replace( /%2F/g, '/' );
  }

  function clampPdfPageNumber( currentValue, delta ) {
    var pageNumber = Number( currentValue || 1 );
    var offset = Number( delta || 0 );
    if ( !Number.isFinite( pageNumber ) || pageNumber < 1 ) {
      pageNumber = 1;
    }
    if ( !Number.isFinite( offset ) ) {
      offset = 0;
    }
    return Math.max( 1, pageNumber + offset );
  }

  function buildLiteratureGuideEditUrl( pageTitle, mwLike ) {
    var title = normalizeString( pageTitle );
    if ( !isLiteratureGuideTitle( title ) ) {
      return '';
    }
    if ( mwLike && mwLike.util && typeof mwLike.util.getUrl === 'function' ) {
      return mwLike.util.getUrl( 'Special:编辑表格/文献导读/' + title );
    }
    return '/wiki/Special:%E7%BC%96%E8%BE%91%E8%A1%A8%E6%A0%BC/%E6%96%87%E7%8C%AE%E5%AF%BC%E8%AF%BB/' +
      encodeURIComponent( title ).replace( /%2F/g, '/' );
  }

  function normalizePdfReaderSource( source ) {
    var item = source || {};
    var type = normalizeString( item.type );
    var url = normalizeString( item.url );
    var fileLabel = normalizeString( item.fileLabel );
    var pageTitle = normalizeString( item.pageTitle );
    if ( type === 'wiki_file' ) {
      var fileTitle = normalizeString( item.fileTitle );
      if ( !fileTitle || !url ) {
        return null;
      }
      return {
        type: 'wiki_file',
        fileTitle: fileTitle,
        url: url,
        fileLabel: fileLabel || stripWikiFilePrefix( fileTitle ),
        pageTitle: pageTitle
      };
    }
    if ( type === 'assistant_attachment' ) {
      var attachmentId = normalizeString( item.attachmentId );
      if ( !attachmentId || !url ) {
        return null;
      }
      return {
        type: 'assistant_attachment',
        attachmentId: attachmentId,
        url: url,
        fileLabel: fileLabel || attachmentId,
        pageTitle: pageTitle
      };
    }
    return null;
  }

  function buildAssistantQuotePrompt( options ) {
    var detail = options || {};
    return [
      '请基于以下 PDF 选区继续解释，并结合当前 Wiki 页面上下文回答。',
      '当前页面：' + normalizeString( detail.pageTitle ),
      'PDF 文件：' + normalizeString( detail.fileLabel ),
      'PDF 页码：' + String( detail.pageNumber || 1 ),
      '引用选区：',
      normalizeString( detail.selectedText )
    ].join( '\n' );
  }

  var exported = {
    buildAssistantQuotePrompt: buildAssistantQuotePrompt,
    buildLiteratureGuideEditUrl: buildLiteratureGuideEditUrl,
    buildWikiFileRedirectUrl: buildWikiFileRedirectUrl,
    clampPdfPageNumber: clampPdfPageNumber,
    isLiteratureGuideTitle: isLiteratureGuideTitle,
    normalizePdfReaderSource: normalizePdfReaderSource,
    stripWikiFilePrefix: stripWikiFilePrefix
  };

  if ( typeof window !== 'undefined' ) {
    window.LabAssistantPdfReaderUtils = exported;
  }
  if ( typeof mw !== 'undefined' ) {
    mw.labassistantPdfReaderUtils = exported;
  }
  if ( typeof module !== 'undefined' && module.exports ) {
    module.exports = exported;
  }
}() );
