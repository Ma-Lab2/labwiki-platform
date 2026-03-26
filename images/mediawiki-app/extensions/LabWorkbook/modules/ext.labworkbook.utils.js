( function () {
  function formatSheetTypeLabel( type ) {
    var labels = {
      main_log: '主台账',
      plan: '打靶计划',
      target_grid: '靶位图',
      calibration: '标定页',
      matrix: '表格页'
    };

    return labels[ type ] || type || '工作表';
  }

  function normalizeDatePart( rawValue ) {
    var value = String( rawValue || '' ).trim();
    var matched = value.match( /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})/ );

    if ( !matched ) {
      return '';
    }

    return [
      matched[ 1 ],
      matched[ 2 ].padStart( 2, '0' ),
      matched[ 3 ].padStart( 2, '0' )
    ].join( '-' );
  }

  function buildShotPageTitle( options ) {
    var runLabel = String( ( options && options.runLabel ) || '' ).trim();
    var row = ( options && options.row ) || {};
    var datePart = normalizeDatePart( row.时间 || row.日期 || row.time || '' );
    var shotNumber = String( row.No || row.NO || row.no || '' ).trim();

    if ( !runLabel || !datePart || !/^\d+$/.test( shotNumber ) ) {
      return '';
    }

    return 'Shot:' + datePart + '-' + runLabel + '-Shot' + shotNumber.padStart( 3, '0' );
  }

  function collectSheetColumns( sheet ) {
    if ( sheet && Array.isArray( sheet.columns ) && sheet.columns.length ) {
      return sheet.columns.slice();
    }

    var seen = [];
    ( ( sheet && sheet.rows ) || [] ).forEach( function ( row ) {
      Object.keys( row || {} ).forEach( function ( key ) {
        if ( seen.indexOf( key ) === -1 ) {
          seen.push( key );
        }
      } );
    } );
    return seen;
  }

  function filterMainLogRows( rows, query ) {
    var normalizedQuery = String( query || '' ).trim().toLowerCase();
    if ( !normalizedQuery ) {
      return ( rows || [] ).slice();
    }

    return ( rows || [] ).filter( function ( row ) {
      return [
        row && row.时间,
        row && row.No,
        row && row.靶类型,
        row && row.靶位,
        row && row.备注
      ].some( function ( value ) {
        return String( value || '' ).toLowerCase().indexOf( normalizedQuery ) !== -1;
      } );
    } );
  }

  var api = {
    buildShotPageTitle: buildShotPageTitle,
    collectSheetColumns: collectSheetColumns,
    filterMainLogRows: filterMainLogRows,
    formatSheetTypeLabel: formatSheetTypeLabel
  };

  if ( typeof module !== 'undefined' && module.exports ) {
    module.exports = api;
  }

  if ( typeof window !== 'undefined' ) {
    window.LabWorkbookUtils = api;
  }
}() );
