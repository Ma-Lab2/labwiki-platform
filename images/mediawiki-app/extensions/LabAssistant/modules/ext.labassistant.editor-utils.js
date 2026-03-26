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
      'PDF文件': [ 'PDF文件', 'PDF', '论文PDF', 'pdf file' ],
      '摘要': [ '摘要', '核心摘要', 'summary' ],
      '相关页面': [ '相关页面', '关联页面', '相关词条' ],
      '来源': [ '来源', '出处', '参考页面' ]
    },
    'Shot记录': {
      '日期': [ '日期', '实验日期', 'shot日期' ],
      'Run': [ 'Run', 'run编号', 'run', 'run号' ],
      '实验目标': [ '实验目标', '本发目标', '目标' ],
      'TPS结果图': [ 'TPS结果图', 'TPS结果截图', 'TPS截图', 'TPS图' ],
      'RCF结果截图': [ 'RCF结果截图', 'RCF结果图', 'RCF截图', 'RCF图' ],
      '判断依据': [ '判断依据', '判据', '判断说明', '结果判据' ],
      '主要观测': [ '主要观测', '结果摘要', '观测摘要', '主要结果' ],
      '周实验日志': [ '周实验日志', '周日志页面', '周日志', '周报页面' ],
      '处理结果文件': [ '处理结果文件', '结果文件', '分析结果文件', '处理文件' ],
      '原始数据主目录': [ '原始数据主目录', '原始数据目录', '数据主目录', '原始数据路径' ]
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

  function extractFormNameFromTitle( value ) {
    var match = String( value || '' ).match( /(?:编辑表格|FormEdit)\/([^/]+)/ );
    return match ? match[ 1 ] : '';
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

  function buildSubmissionGuidanceStorageKey( title, host ) {
    return 'labassistant-submission-guidance::' + String( host || '' ) + '::' + String( title || '' );
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
      var rawValue = suggestions[ key ];
      var status = 'matched';
      var evidence = [];
      var reason = '';
      var value = rawValue;
      if ( rawValue && typeof rawValue === 'object' && !Array.isArray( rawValue ) ) {
        value = rawValue.value;
        status = String( rawValue.status || '' ).trim().toLowerCase() || 'matched';
        reason = String( rawValue.reason || '' ).trim();
        evidence = Array.isArray( rawValue.evidence ) ?
          rawValue.evidence.map( function ( item ) {
            return String( item || '' ).trim();
          } ).filter( Boolean ) :
          [];
      }
      entries.push( {
        originalKey: key,
        normalizedKey: normalizeFieldName( key ),
        value: value,
        status: status,
        evidence: evidence,
        reason: reason
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

  function extractDatePartValue( rawValue, label ) {
    var match = String( rawValue || '' ).trim().match( /^(\d{4})-(\d{2})-(\d{2})$/ );
    var normalizedLabel = normalizeFieldName( label );
    if ( !match ) {
      return '';
    }
    if ( normalizedLabel.indexOf( normalizeFieldName( '日期][year' ) ) === 0 ) {
      return match[ 1 ];
    }
    if ( normalizedLabel.indexOf( normalizeFieldName( '日期][month' ) ) === 0 ) {
      return match[ 2 ];
    }
    if ( normalizedLabel.indexOf( normalizeFieldName( '日期][day' ) ) === 0 ) {
      return match[ 3 ];
    }
    return '';
  }

  function isShotDatePartLabel( label ) {
    return /日期\]\[(day|month|year)$/i.test( String( label || '' ) );
  }

  function matchStructuredFieldsToInventory( formName, suggestions, inventory ) {
    var aliasesByCanonical = getCanonicalFieldNames( formName ) || {};
    var suggestionEntries = normalizeStructuredFieldMap( suggestions );

    return ( inventory || [] ).map( function ( field ) {
      var label = field.label || '';
      var normalizedLabel = normalizeFieldName( label );
      var canonicalName = Object.keys( aliasesByCanonical ).find( function ( candidate ) {
        var aliases = aliasesByCanonical[ candidate ] || [];
        return aliases.map( normalizeFieldName ).indexOf( normalizedLabel ) !== -1;
      } ) || label;
      var aliases = aliasesByCanonical[ canonicalName ] || [ canonicalName, label ];
      var match = findSuggestionForField( aliases, suggestionEntries );
      var value;
      if ( !match && formName === 'Shot记录' && isShotDatePartLabel( label ) ) {
        match = findSuggestionForField( aliasesByCanonical.日期 || [ '日期' ], suggestionEntries );
      }
      if ( !match ) {
        return null;
      }
      if ( formName === 'Shot记录' && isShotDatePartLabel( label ) ) {
        value = extractDatePartValue( match.value, label );
      } else {
        value = MULTI_VALUE_CONTROLS[ field.controlType ] ? splitSuggestedValues( match.value ) : String( match.value || '' ).trim();
      }
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
      var output = {
        fieldKey: field.key,
        fieldLabel: label,
        suggestionKey: match.originalKey,
        value: value,
        controlType: field.controlType || 'text',
        status: match.status || 'matched'
      };
      if ( match.evidence && match.evidence.length ) {
        output.evidence = match.evidence;
      }
      if ( match.reason ) {
        output.reason = match.reason;
      }
      return output;
    } ).filter( Boolean );
  }

  function resolvePageFormRuntimeContext( options ) {
    var context = options || {};
    var editorMode = context.editorMode || 'default';
    var resolvedFormName = String( context.resolvedFormName || '' ).trim();
    var pageFormFields = Array.isArray( context.pageFormFields ) ? context.pageFormFields : [];
    var hasPageFormRoot = !!context.hasPageFormRoot;

    if ( !resolvedFormName ) {
      resolvedFormName = String(
        ( context.formContext && context.formContext.formName ) ||
        extractFormNameFromTitle( context.currentTitle ) ||
        ''
      ).trim();
    }

    if ( hasPageFormRoot && editorMode === 'default' ) {
      editorMode = 'pageforms_edit';
    }

    if (
      hasPageFormRoot &&
      editorMode === 'pageforms_edit' &&
      !pageFormFields.length &&
      typeof context.collectPageFormFields === 'function'
    ) {
      pageFormFields = context.collectPageFormFields() || [];
    }

    return {
      editorMode: editorMode,
      resolvedFormName: resolvedFormName,
      pageFormFields: pageFormFields
    };
  }

  function buildFormFillNotice( matches ) {
    var labels = normalizeFieldLabels( ( matches || [] ).map( function ( match ) {
      return String( match && match.fieldLabel || '' ).trim();
    } ) );

    if ( !labels.length ) {
      return '没有可填入的字段。';
    }

    return (
      '已填入 ' +
      labels.length +
      ' 个表单字段：' +
      labels.join( '、' ) +
      '；表单尚未提交。'
    );
  }

  function normalizeFieldLabels( labels ) {
    return normalizeMissingItemEntries( labels ).map( function ( entry ) {
      return entry.label;
    } );
  }

  function normalizeMissingItemEntries( items ) {
    var normalized = [];
    ( items || [] ).forEach( function ( item ) {
      var rawLabel = '';
      var label = '';
      var reason = '';
      var evidence = [];
      var existing;
      if ( item && typeof item === 'object' && !Array.isArray( item ) ) {
        rawLabel = item.label || item.field || item.name || '';
        reason = String( item.reason || item.note || item.message || '' ).trim();
        evidence = Array.isArray( item.evidence ) ?
          item.evidence.map( function ( evidenceItem ) {
            return String( evidenceItem || '' ).trim();
          } ).filter( Boolean ) :
          [];
      } else {
        rawLabel = item;
      }
      label = String( rawLabel || '' ).trim().replace( /\]\[(?:day|month|year)$/i, '' );
      if ( !label ) {
        return;
      }
      existing = normalized.find( function ( entry ) {
        return entry.label === label;
      } );
      if ( existing ) {
        if ( !existing.reason && reason ) {
          existing.reason = reason;
        }
        evidence.forEach( function ( evidenceItem ) {
          if ( existing.evidence.indexOf( evidenceItem ) === -1 ) {
            existing.evidence.push( evidenceItem );
          }
        } );
        return;
      }
      normalized.push( {
        label: label,
        reason: reason,
        evidence: evidence
      } );
    } );
    return normalized;
  }

  function buildSubmissionChecklistNotice( labels, options ) {
    var normalizedLabels = normalizeFieldLabels( labels );
    var preface = String( options && options.preface || '' ).trim();
    if ( !normalizedLabels.length ) {
      return '';
    }
    return [
      preface,
      '提交前请确认：' + normalizedLabels.join( '、' ) + '；这些项还没有自动补全。'
    ].filter( Boolean ).join( ' ' );
  }

  function buildSubmissionChecklistSections( pendingItems, missingItems, options ) {
    var preface = String( options && options.preface || '' ).trim();
    var normalizedPendingItems = normalizeMissingItemEntries( pendingItems ).map( function ( entry ) {
      return {
        label: entry.label,
        reason: entry.reason || '已有候选值，请学生确认后再提交。',
        evidence: Array.isArray( entry.evidence ) ? entry.evidence : []
      };
    } );
    var pendingNames = normalizedPendingItems.map( function ( entry ) {
      return normalizeFieldName( entry.label );
    } );
    var normalizedMissingItems = normalizeMissingItemEntries( missingItems )
      .filter( function ( entry ) {
        return pendingNames.indexOf( normalizeFieldName( entry.label ) ) === -1;
      } )
      .map( function ( entry ) {
        return {
          label: entry.label,
          reason: entry.reason || '当前还没有可直接回填的候选值。',
          evidence: Array.isArray( entry.evidence ) ? entry.evidence : []
        };
      } );
    var pendingText = normalizedPendingItems.length ?
      '提交前请确认：' +
        normalizedPendingItems.map( function ( entry ) {
          return entry.label;
        } ).join( '、' ) +
        '；这些字段已有候选值，但仍需学生确认。' :
      '';
    var missingText = normalizedMissingItems.length ?
      '提交前请补充：' +
        normalizedMissingItems.map( function ( entry ) {
          return entry.label;
        } ).join( '、' ) +
        '；当前还没有可直接回填的候选值。' :
      '';

    return {
      preface: preface,
      pendingItems: normalizedPendingItems,
      missingItems: normalizedMissingItems,
      pendingText: pendingText,
      missingText: missingText,
      summaryText: [ preface, pendingText, missingText ].filter( Boolean ).join( ' ' )
    };
  }

  function buildResultFillFieldSections( suggestions, missingItems ) {
    var normalizedMissingEntries = normalizeMissingItemEntries( missingItems );
    var normalizedMissingLabels = normalizedMissingEntries.map( function ( entry ) {
      return entry.label;
    } );
    var normalizedMissingNames = normalizedMissingLabels.map( normalizeFieldName );
    var resolvedSuggestionNames = [];
    var confirmed = [];
    var pending = [];

    function buildSectionEntry( label, value, evidence, reason ) {
      var entry = {
        label: label,
        value: value
      };
      if ( evidence && evidence.length ) {
        entry.evidence = evidence;
      }
      if ( reason ) {
        entry.reason = reason;
      }
      return entry;
    }

    Object.keys( suggestions || {} ).forEach( function ( key ) {
      var label = String( key || '' ).trim();
      var normalizedLabel = normalizeFieldName( label );
      var suggestion = suggestions[ key ];
      var rawValue = suggestion;
      var value;
      var evidence = [];
      var reason = '';
      var status = '';
      var isPendingStatus;
      var normalizedDisplayLabel;
      var isMissing;
      if ( suggestion && typeof suggestion === 'object' && !Array.isArray( suggestion ) ) {
        rawValue = suggestion.value;
        evidence = Array.isArray( suggestion.evidence ) ?
          suggestion.evidence.map( function ( item ) {
            return String( item || '' ).trim();
          } ).filter( Boolean ) :
          [];
        reason = String( suggestion.reason || '' ).trim();
        status = String( suggestion.status || '' ).trim().toLowerCase();
      }
      value = Array.isArray( rawValue ) ?
        rawValue.map( function ( item ) {
          return String( item || '' ).trim();
        } ).filter( Boolean ).join( '；' ) :
        String( rawValue || '' ).trim();
      normalizedDisplayLabel = normalizeFieldLabels( [ label ] )[ 0 ] || label;

      if ( !label || !normalizedLabel ) {
        return;
      }

      isMissing = normalizedMissingNames.indexOf( normalizedLabel ) !== -1;
      if ( !value || isLowConfidenceAutofillValue( value ) ) {
        if ( isMissing && normalizedMissingLabels.indexOf( normalizedDisplayLabel ) === -1 ) {
          normalizedMissingLabels.push( normalizedDisplayLabel );
          normalizedMissingNames.push( normalizedLabel );
        }
        return;
      }
      if ( resolvedSuggestionNames.indexOf( normalizedLabel ) === -1 ) {
        resolvedSuggestionNames.push( normalizedLabel );
      }
      isPendingStatus = status === 'pending' || status === 'needs_review';
      if ( isMissing || isPendingStatus ) {
        pending.push( buildSectionEntry( normalizedDisplayLabel, value, evidence, reason ) );
        return;
      }
      confirmed.push( buildSectionEntry( normalizedDisplayLabel, value, evidence, reason ) );
    } );

    return {
      confirmed: confirmed,
      pending: pending,
      missing: normalizedMissingLabels.filter( function ( label ) {
        return resolvedSuggestionNames.indexOf( normalizeFieldName( label ) ) === -1;
      } )
    };
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
    buildSubmissionGuidanceStorageKey: buildSubmissionGuidanceStorageKey,
    buildFormFillNotice: buildFormFillNotice,
    buildResultFillFieldSections: buildResultFillFieldSections,
    buildSubmissionChecklistSections: buildSubmissionChecklistSections,
    buildSubmissionChecklistNotice: buildSubmissionChecklistNotice,
    detectEditorMode: detectEditorMode,
    extractFormNameFromTitle: extractFormNameFromTitle,
    normalizeFieldLabels: normalizeFieldLabels,
    resolvePageFormRuntimeContext: resolvePageFormRuntimeContext,
    matchStructuredFieldsToInventory: matchStructuredFieldsToInventory,
    isLowConfidenceAutofillValue: isLowConfidenceAutofillValue,
    normalizeFieldName: normalizeFieldName,
    normalizeMissingItemEntries: normalizeMissingItemEntries,
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
