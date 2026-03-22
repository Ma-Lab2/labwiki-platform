( function () {
  var MULTI_VALUE_CONTROLS = {
    tokens: true,
    multiselect: true
  };

  var FORM_FIELD_ALIASES = {
    '术语条目': {
      '中文名': [ '中文名', '术语名称', '名称' ],
      '英文名': [ '英文名', '英文名称', 'english name' ],
      '缩写': [ '缩写', '简称', 'abbreviation' ],
      '摘要': [ '摘要', '定义', '说明' ],
      '别名': [ '别名', '同义词', '别称' ],
      '关联页面': [ '关联页面', '相关页面', '关联词条' ],
      '来源': [ '来源', '出处', '参考页面' ]
    },
    '设备条目': {
      '设备名称': [ '设备名称', '名称', '设备名' ],
      '系统归属': [ '系统归属', '归属系统', '系统' ],
      '关键参数': [ '关键参数', '主要参数', '参数' ],
      '用途': [ '用途', '作用', '使用场景' ],
      '运行页': [ '运行页', '运行页面', '操作页面' ],
      '来源': [ '来源', '出处', '参考页面' ]
    },
    '诊断条目': {
      '诊断名称': [ '诊断名称', '名称', '诊断名' ],
      '测量对象': [ '测量对象', '对象', '观测对象' ],
      '主要输出': [ '主要输出', '输出', '结果' ],
      '易错点': [ '易错点', '注意事项', '常见问题' ],
      '工具入口': [ '工具入口', '入口', '工具页面' ],
      '来源': [ '来源', '出处', '参考页面' ]
    },
    '文献导读': {
      '标题': [ '标题', '文献标题', '题目' ],
      '作者': [ '作者', '作者列表', 'authors' ],
      '年份': [ '年份', '发表年份', 'year' ],
      'DOI': [ 'doi', 'DOI' ],
      '摘要': [ '摘要', '核心摘要', 'summary' ],
      '相关页面': [ '相关页面', '关联页面', '相关词条' ],
      '来源': [ '来源', '出处', '参考页面' ]
    }
  };

  function normalizeFieldName( value ) {
    return String( value || '' )
      .trim()
      .toLowerCase()
      .replace( /[:：]/g, '' )
      .replace( /[()[\]{}]/g, ' ' )
      .replace( /[·•,，;；/\\|]/g, ' ' )
      .replace( /\s+/g, '' );
  }

  function detectEditorMode( config ) {
    if ( config && config.editorMode ) {
      return config.editorMode;
    }
    if ( config && config.currentVeAction ) {
      return 'visual_editor';
    }
    if ( config && ( config.currentAction === 'formedit' || config.specialPageName === 'FormEdit' ) ) {
      return 'pageforms_edit';
    }
    if ( config && config.currentAction === 'edit' ) {
      return 'source_edit';
    }
    return 'default';
  }

  function buildDraftHandoffStorageKey( title, host ) {
    return 'labassistant-draft-handoff::' + String( host || '' ) + '::' + String( title || '' );
  }

  function splitSuggestedValues( value ) {
    if ( Array.isArray( value ) ) {
      return value
        .map( function ( item ) {
          return String( item || '' ).trim();
        } )
        .filter( Boolean );
    }
    return String( value || '' )
      .split( /[；;、\n]/ )
      .map( function ( item ) {
        return item.trim();
      } )
      .filter( Boolean );
  }

  function isLowConfidenceAutofillValue( value ) {
    var normalized = String( value || '' )
      .trim()
      .toLowerCase()
      .replace( /\s+/g, '' );

    if ( !normalized ) {
      return true;
    }

    return (
      normalized === '待补充' ||
      normalized === '待确认' ||
      normalized === '无' ||
      normalized === '暂无' ||
      normalized === '未知' ||
      normalized === '未提供' ||
      normalized === '未说明' ||
      normalized === '未明确' ||
      normalized === '表单上下文' ||
      normalized === 'n/a' ||
      normalized === 'na' ||
      normalized === 'unknown' ||
      normalized === 'notprovided' ||
      normalized.indexOf( '待补充' ) === 0 ||
      normalized.indexOf( '待确认' ) === 0 ||
      normalized.indexOf( '待页面' ) === 0
    );
  }

  function normalizeStructuredFieldMap( suggestions ) {
    var entries = [];
    Object.keys( suggestions || {} ).forEach( function ( key ) {
      entries.push( {
        originalKey: key,
        normalizedKey: normalizeFieldName( key ),
        value: suggestions[ key ]
      } );
    } );
    return entries;
  }

  function getCanonicalFieldNames( formName ) {
    return FORM_FIELD_ALIASES[ formName ] || null;
  }

  function findSuggestionForField( aliases, suggestionEntries ) {
    var normalizedAliases = aliases.map( normalizeFieldName );
    return suggestionEntries.find( function ( entry ) {
      return normalizedAliases.indexOf( entry.normalizedKey ) !== -1;
    } ) || null;
  }

  function matchStructuredFieldsToInventory( formName, suggestions, inventory ) {
    var aliasesByCanonical = getCanonicalFieldNames( formName ) || {};
    var suggestionEntries = normalizeStructuredFieldMap( suggestions );

    return ( inventory || [] ).map( function ( field ) {
      var label = field.label || '';
      var canonicalName = Object.keys( aliasesByCanonical ).find( function ( candidate ) {
        var aliases = aliasesByCanonical[ candidate ] || [];
        return aliases.map( normalizeFieldName ).indexOf( normalizeFieldName( label ) ) !== -1;
      } ) || label;
      var aliases = aliasesByCanonical[ canonicalName ] || [ canonicalName, label ];
      var match = findSuggestionForField( aliases, suggestionEntries );
      if ( !match ) {
        return null;
      }
      var value = MULTI_VALUE_CONTROLS[ field.controlType ] ? splitSuggestedValues( match.value ) : String( match.value || '' ).trim();
      if ( MULTI_VALUE_CONTROLS[ field.controlType ] ) {
        value = value.filter( function ( item ) {
          return !isLowConfidenceAutofillValue( item );
        } );
        if ( !value.length ) {
          return null;
        }
      } else if ( isLowConfidenceAutofillValue( value ) ) {
        return null;
      }
      return {
        fieldKey: field.key,
        fieldLabel: label,
        suggestionKey: match.originalKey,
        value: value,
        controlType: field.controlType || 'text',
        status: 'matched'
      };
    } ).filter( Boolean );
  }

  function parseStructuredFieldSuggestions( source ) {
    var suggestions = {};
    String( source || '' )
      .replace( /\r\n?/g, '\n' )
      .split( '\n' )
      .forEach( function ( line ) {
        var trimmed = line.trim();
        var match;
        if ( !trimmed ) {
          return;
        }
        match = trimmed.match( /^(?:[-*]\s*)?([^:：]+)\s*[:：]\s*(.+)$/ );
        if ( !match ) {
          return;
        }
        suggestions[ match[ 1 ].trim() ] = match[ 2 ].trim();
      } );
    return suggestions;
  }

  function parseMissingFields( source ) {
    var missing = [];
    String( source || '' )
      .replace( /\r\n?/g, '\n' )
      .split( '\n' )
      .forEach( function ( line ) {
        var trimmed = line.trim();
        var match;
        if ( !trimmed ) {
          return;
        }
        match = trimmed.match( /^(?:[-*]\s*)?缺失字段\s*[:：]\s*(.+)$/ );
        if ( !match ) {
          return;
        }
        match[ 1 ]
          .split( /[；;、，,\n]/ )
          .map( function ( item ) {
            return item.trim();
          } )
          .filter( function ( item ) {
            return item && item !== '无' && item !== '暂无' && item !== '无明显缺失';
          } )
          .forEach( function ( item ) {
            if ( missing.indexOf( item ) === -1 ) {
              missing.push( item );
            }
          } );
      } );
    return missing;
  }

  var exported = {
    buildDraftHandoffStorageKey: buildDraftHandoffStorageKey,
    detectEditorMode: detectEditorMode,
    matchStructuredFieldsToInventory: matchStructuredFieldsToInventory,
    isLowConfidenceAutofillValue: isLowConfidenceAutofillValue,
    normalizeFieldName: normalizeFieldName,
    parseMissingFields: parseMissingFields,
    parseStructuredFieldSuggestions: parseStructuredFieldSuggestions
  };

  if ( typeof module !== 'undefined' && module.exports ) {
    module.exports = exported;
  }

  if ( typeof window !== 'undefined' ) {
    window.LabAssistantEditorUtils = exported;
    if ( window.mw ) {
      window.mw.labassistantEditorUtils = exported;
    }
  }
}() );
