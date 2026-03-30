( function () {
  var DEFAULT_THEME = 'deep-space-window';
  var THEME_HINT_COOKIE = 'labwiki_private_theme_hint';
  var APPEARANCE_SETTINGS_FALLBACK = 'Special:参数设置#mw-prefsection-rendering-skin';
  var THEMES = [
    {
      id: 'deep-space-window',
      name: '深空蓝窗',
      summary: '夜间观测窗，深蓝、月白和冷光玻璃。'
    },
    {
      id: 'polar-silver-blue',
      name: '极地银蓝',
      summary: '像设备控制台，雾银、钢蓝和低对比冷光。'
    },
    {
      id: 'cyan-tide-glow',
      name: '青色波光',
      summary: '午夜蓝与青色波纹，更灵动但仍保持克制。'
    }
  ];
  var MENU_GROUPS = {
    '工作台': [
      { title: '日常入口', items: [ '首页', '知识助手', '实验工作簿' ] },
      { title: '实验记录', items: [ 'Shot 日志入口', '周实验日志', '数据关联规则' ] },
      { title: '执行 SOP', items: [ '打靶 SOP', '10 分钟检查清单' ] }
    ],
    '理论': [
      { title: '总览与路径', items: [ '理论总览', '新人学习路径', '激光-等离子体相互作用基础', '加速总览' ] },
      { title: '机制', items: [ 'TNSA', 'RPA', 'CSA / ESA', '透明化机制', 'MVA', '机制判别图谱' ] },
      { title: '尺度与预等离子体', items: [ '尺度律与开放问题', '对比度与预等离子体' ] }
    ],
    'SOP 与安全': [
      { title: 'SOP 流程', items: [ 'SOP 总览', '主靶室打靶流程', '打靶前安全检查', '10 分钟检查清单', '安全高效打靶三步走' ] },
      { title: '安全规范', items: [ '安全总览', '激光安全', '真空操作', '腔体操作', '靶场安全事项' ] }
    ],
    '激光与靶场': [
      { title: '激光理论', items: [ '激光系统总览', '超快激光基础理论', '高功率链路理论', '波前与聚焦理论', '光学元件原理' ] },
      { title: '激光诊断与元件', items: [ '激光链路总图', '三阶自相关与对比度', '波前与可变形镜' ] },
      { title: '靶场系统', items: [ '靶场总览', '靶区传输光路', '靶架与找靶', '束靶耦合段', '主靶室', 'RCF运动系统' ] }
    ],
    '诊断与数据': [
      { title: '诊断工具', items: [ '诊断总览', '超快诊断理论', 'TPS 分析工具', 'RCF 计算工具' ] },
      { title: '数据管理', items: [ '数据管理总览', '实验工作簿说明', '实验日志与数据关联', 'TPS 归档规则', 'RCF 归档规则', '数据归档' ] }
    ],
    '项目与复盘': [
      { title: '项目', items: [ '项目总览', '激光质子加速' ] },
      { title: '复盘与问题', items: [ '新建 Shot 记录', '会议入口', '实验复盘模板', '风险与问题' ] }
    ],
    '运行支持': [
      { title: '平台控制', items: [ '中央控制平台', '继电器系统', '照明与监控', '知识助手管理' ] },
      { title: '条目索引', items: [ '术语条目索引', '设备条目索引', '机制条目索引', '诊断条目索引', '文献导读索引' ] },
      { title: '运维与 FAQ', items: [ '受限信息索引', '值班与排班', '仪器台账', '常见问题', '公式与引用速查', '知识助手说明' ] }
    ]
  };
  var DEFAULT_MENU_STATE = {
    section: '工作台'
  };
  var shellCounter = 0;
  var refreshPending = false;

  function getThemeMeta( id ) {
    return THEMES.find( function ( theme ) {
      return theme.id === id;
    } ) || THEMES[ 0 ];
  }

  function applyTheme( id ) {
    var themeId = getThemeMeta( id ).id;
    document.documentElement.setAttribute( 'data-labwiki-private', '1' );
    document.documentElement.setAttribute( 'data-labwiki-theme', themeId );
    if ( window.document ) {
      document.cookie = THEME_HINT_COOKIE + '=' + encodeURIComponent( themeId ) + '; path=/; max-age=31536000; SameSite=Lax';
    }
    return themeId;
  }

  function readThemeHint() {
    var match = document.cookie.match( new RegExp( '(?:^|; )' + THEME_HINT_COOKIE + '=([^;]+)' ) );

    if ( !match || !match[ 1 ] ) {
      return null;
    }

    try {
      return decodeURIComponent( match[ 1 ] );
    } catch ( error ) {
      return null;
    }
  }

  function syncThemeFromUserOptions() {
    var preferredTheme;

    if ( !window.mw || !mw.user || !mw.user.options || typeof mw.user.options.get !== 'function' ) {
      return;
    }

    preferredTheme = mw.user.options.get( 'labwiki-private-theme' );
    if ( preferredTheme && preferredTheme !== document.documentElement.getAttribute( 'data-labwiki-theme' ) ) {
      applyTheme( preferredTheme );
    }
  }

  function getAppearanceSettingsUrl() {
    var configured = document.documentElement.getAttribute( 'data-labwiki-appearance-settings-url' );

    if ( configured ) {
      return configured;
    }

    if ( window.mw && mw.util && typeof mw.util.getUrl === 'function' ) {
      return mw.util.getUrl( 'Special:Preferences' ) + '#mw-prefsection-rendering-skin';
    }

    return '/index.php?title=' + encodeURIComponent( APPEARANCE_SETTINGS_FALLBACK );
  }

  var initialTheme = document.documentElement.getAttribute( 'data-labwiki-theme' );
  if ( initialTheme ) {
    applyTheme( initialTheme );
  } else {
    initialTheme = readThemeHint();
    if ( initialTheme ) {
      applyTheme( initialTheme );
    }
  }

  syncThemeFromUserOptions();
  if ( window.mw && mw.loader && typeof mw.loader.using === 'function' ) {
    mw.loader.using( 'user.options' ).then( function () {
      syncThemeFromUserOptions();
    } ).catch( function () {} );
  }

  function normalizeText( text ) {
    return ( text || '' ).replace( /\s+/g, ' ' ).trim();
  }

  function isLegacyAppearanceItem( href, text ) {
    return href.indexOf( 'useskin=vector' ) !== -1 || text.indexOf( '切换到旧外观' ) !== -1;
  }

  function normalizeWikiTitle( title ) {
    return normalizeText(
      decodeURIComponent( String( title || '' ).replace( /\+/g, '%20' ) )
    ).replace( / /g, '_' );
  }

  function getCurrentPageCandidates() {
    var currentUrl = new URL( window.location.href, window.location.origin );

    return {
      href: currentUrl.href,
      path: currentUrl.pathname + currentUrl.search,
      pathname: currentUrl.pathname,
      title: normalizeWikiTitle( currentUrl.searchParams.get( 'title' ) )
    };
  }

  function matchesCurrentLocation( href, currentPage ) {
    var resolved;
    var resolvedTitle;

    if ( !href || !currentPage ) {
      return false;
    }

    try {
      resolved = new URL( href, window.location.origin );
    } catch ( error ) {
      return false;
    }

    if ( resolved.href === currentPage.href ||
      resolved.pathname + resolved.search === currentPage.path ) {
      return true;
    }

    resolvedTitle = normalizeWikiTitle( resolved.searchParams.get( 'title' ) );

    if ( resolvedTitle && currentPage.title && resolvedTitle === currentPage.title ) {
      return true;
    }

    return !resolved.search && resolved.pathname === currentPage.pathname;
  }

  function getGroupConfigs( sectionTitle ) {
    return MENU_GROUPS[ sectionTitle ] || [];
  }

  function extractMenuSections( sourceMenu ) {
    var sections = [];
    var currentPage = getCurrentPageCandidates();

    Array.prototype.slice.call( sourceMenu.querySelectorAll( '.vector-menu.mw-portlet' ) ).forEach( function ( menu ) {
      var heading = menu.querySelector( '.vector-menu-heading-label, .vector-menu-heading' );
      var title = normalizeText( heading && heading.textContent );
      var items = [];

      Array.prototype.slice.call( menu.querySelectorAll( '.mw-list-item' ) ).forEach( function ( item ) {
        var link = item.querySelector( 'a' );
        var href = link && link.getAttribute( 'href' ) || '';
        var text = normalizeText( link && link.textContent );

        if ( !link || !text || isLegacyAppearanceItem( href, text ) ) {
          return;
        }

        items.push( {
          href: href,
          isCurrent: item.classList.contains( 'selected' ) ||
            item.classList.contains( 'active' ) ||
            link.getAttribute( 'aria-current' ) === 'page' ||
            matchesCurrentLocation( href, currentPage ),
          text: text
        } );
      } );

      if ( title && items.length ) {
        sections.push( {
          items: items,
          title: title
        } );
      }
    } );

    return sections;
  }

  function buildSectionModel( section ) {
    var orderLookup = {};
    var hasActive = false;
    var nextIndex = 0;

    getGroupConfigs( section.title ).forEach( function ( config ) {
      config.items.forEach( function ( itemText ) {
        if ( typeof orderLookup[ itemText ] === 'undefined' ) {
          orderLookup[ itemText ] = nextIndex++;
        }
      } );
    } );

    section.items.forEach( function ( item ) {
      if ( typeof orderLookup[ item.text ] === 'undefined' ) {
        orderLookup[ item.text ] = nextIndex++;
      }

      if ( item.isCurrent ) {
        hasActive = true;
      }
    } );

    return {
      items: section.items.slice().sort( function ( left, right ) {
        return orderLookup[ left.text ] - orderLookup[ right.text ];
      } ),
      hasActive: hasActive,
      itemCount: section.items.length,
      title: section.title
    };
  }

  function deriveInitialMenuState( sections ) {
    var index;

    for ( index = 0; index < sections.length; index++ ) {
      if ( sections[ index ].hasActive ) {
        return {
          section: sections[ index ].title
        };
      }
    }

    for ( index = 0; index < sections.length; index++ ) {
      if ( sections[ index ].title === DEFAULT_MENU_STATE.section ) {
        return {
          section: sections[ index ].title
        };
      }
    }

    if ( sections.length ) {
      return {
        section: sections[ 0 ].title
      };
    }

    return {
      section: ''
    };
  }

  function createChevron() {
    var chevron = document.createElement( 'span' );
    chevron.className = 'labwiki-sidebar-chevron';
    chevron.setAttribute( 'aria-hidden', 'true' );
    return chevron;
  }

  function createCounter( count ) {
    var counter = document.createElement( 'span' );
    counter.className = 'labwiki-sidebar-counter';
    counter.textContent = String( count );
    counter.setAttribute( 'aria-hidden', 'true' );
    return counter;
  }

  function renderLinkList( section ) {
    var list = document.createElement( 'ul' );

    list.className = 'labwiki-sidebar-links';
    section.items.forEach( function ( item ) {
      var listItem = document.createElement( 'li' );
      var link = document.createElement( 'a' );

      listItem.className = 'labwiki-sidebar-link-item';
      link.className = 'labwiki-sidebar-link';
      link.href = item.href;
      link.textContent = item.text;

      if ( item.isCurrent ) {
        link.classList.add( 'is-active' );
        link.setAttribute( 'aria-current', 'page' );
      }

      listItem.appendChild( link );
      list.appendChild( listItem );
    } );

    return list;
  }

  function renderSection( shellId, section, initialState, sectionIndex ) {
    var sectionNode = document.createElement( 'section' );
    var toggle = document.createElement( 'button' );
    var label = document.createElement( 'span' );
    var panel = renderLinkList( section );
    var isOpen = section.title === initialState.section;

    sectionNode.className = 'labwiki-sidebar-section';
    sectionNode.setAttribute( 'data-section-title', section.title );
    toggle.className = 'labwiki-sidebar-section-toggle';
    toggle.type = 'button';
    toggle.setAttribute( 'aria-controls', shellId + '-section-' + sectionIndex );
    toggle.setAttribute( 'aria-expanded', isOpen ? 'true' : 'false' );
    label.className = 'labwiki-sidebar-section-title';
    label.textContent = section.title;
    toggle.appendChild( label );
    toggle.appendChild( createCounter( section.itemCount ) );
    toggle.appendChild( createChevron() );
    panel.classList.add( 'labwiki-sidebar-section-panel' );
    panel.id = shellId + '-section-' + sectionIndex;
    panel.hidden = !isOpen;

    sectionNode.appendChild( toggle );
    sectionNode.appendChild( panel );

    if ( isOpen ) {
      sectionNode.classList.add( 'is-open' );
    }

    if ( section.hasActive ) {
      sectionNode.classList.add( 'has-active' );
    }

    return sectionNode;
  }

  function setSectionExpanded( sectionNode, expanded ) {
    var button = sectionNode.children[ 0 ];
    var panel = sectionNode.children[ 1 ];

    sectionNode.classList.toggle( 'is-open', expanded );
    button.setAttribute( 'aria-expanded', expanded ? 'true' : 'false' );
    panel.hidden = !expanded;
  }

  function bindAccordionBehavior( wrapper ) {
    wrapper.addEventListener( 'click', function ( event ) {
      var sectionButton = event.target.closest( '.labwiki-sidebar-section-toggle' );
      var sectionNode;

      if ( sectionButton && wrapper.contains( sectionButton ) ) {
        sectionNode = sectionButton.parentNode;

        Array.prototype.slice.call( wrapper.querySelectorAll( '.labwiki-sidebar-section' ) ).forEach( function ( sibling ) {
          setSectionExpanded(
            sibling,
            sibling === sectionNode && sectionButton.getAttribute( 'aria-expanded' ) !== 'true'
          );
        } );
      }
    } );
  }

  function buildKnowledgeTreeShell( sourceMenu ) {
    var sections = extractMenuSections( sourceMenu ).map( buildSectionModel ).filter( function ( section ) {
      return section.items.length;
    } );
    var wrapper;
    var accordion;
    var initialState;
    var shellId;

    if ( !sections.length ) {
      return null;
    }

    shellId = 'labwiki-sidebar-' + ( ++shellCounter );
    initialState = deriveInitialMenuState( sections );
    wrapper = document.createElement( 'div' );
    wrapper.className = 'labwiki-sidebar-shell';
    wrapper.innerHTML =
      '<div class="labwiki-sidebar-header">' +
      '<strong>课题组知识树</strong>' +
      '</div>';
    accordion = document.createElement( 'div' );
    accordion.className = 'labwiki-sidebar-accordion';
    sections.forEach( function ( section, sectionIndex ) {
      accordion.appendChild( renderSection( shellId, section, initialState, sectionIndex ) );
    } );
    wrapper.appendChild( accordion );
    bindAccordionBehavior( wrapper );

    return wrapper;
  }

  function removeLegacyAppearanceLinks() {
    Array.prototype.slice.call( document.querySelectorAll( 'a' ) ).forEach( function ( link ) {
      var href = link.getAttribute( 'href' ) || '';
      var text = link.textContent || '';
      var item = link.closest( '.mw-list-item' );

      if ( href.indexOf( 'useskin=vector' ) === -1 && text.indexOf( '切换到旧外观' ) === -1 ) {
        return;
      }

      if ( item ) {
        item.remove();
      } else {
        link.remove();
      }
    } );
  }

  function setNodeTextIfNeeded( node, value ) {
    if ( node && normalizeText( node.textContent ) !== value ) {
      node.textContent = value;
    }
  }

  function setAttributeIfNeeded( node, name, value ) {
    if ( node && node.getAttribute( name ) !== value ) {
      node.setAttribute( name, value );
    }
  }

  function mountKnowledgeTreeInto( sourceMenu, target ) {
    var wrapper;

    if ( !target || target.querySelector( '.labwiki-sidebar-shell' ) ) {
      return;
    }

    wrapper = buildKnowledgeTreeShell( sourceMenu );

    if ( !wrapper ) {
      return;
    }

    if ( target.id === 'vector-main-menu-unpinned-container' ) {
      wrapper.classList.add( 'labwiki-sidebar-shell--dropdown' );
    }

    target.appendChild( wrapper );
  }

  function renameKnowledgeTreeTrigger() {
    var checkbox = document.querySelector( '#vector-main-menu-dropdown-checkbox' );
    var label = document.querySelector( '#vector-main-menu-dropdown-label' );
    var labelText = document.querySelector( '#vector-main-menu-dropdown .vector-dropdown-label-text' );
    var pinnableHeaderLabel = document.querySelector(
      '#vector-main-menu-unpinned-container .vector-main-menu-pinnable-header .vector-pinnable-header-label'
    );

    setNodeTextIfNeeded( labelText, '知识树' );
    setNodeTextIfNeeded( pinnableHeaderLabel, '知识树' );
    setAttributeIfNeeded( checkbox, 'aria-label', '知识树' );
    setAttributeIfNeeded( label, 'aria-label', '知识树' );
    setAttributeIfNeeded( label, 'title', '知识树' );
  }

  function resolveMountTargets() {
    var pinnedTarget = document.querySelector( '#vector-main-menu-pinned-container' );
    var unpinnedTarget = document.querySelector( '#vector-main-menu-unpinned-container' );
    var isCompactViewport = window.matchMedia && window.matchMedia( '(max-width: 999px)' ).matches;

    if ( isCompactViewport ) {
      return [ unpinnedTarget ];
    }

    return [ pinnedTarget, unpinnedTarget ].filter( function ( target, index, targets ) {
      return target && targets.indexOf( target ) === index;
    } );
  }

  function clearInactiveKnowledgeTreeShells( activeTargets ) {
    Array.prototype.slice.call( document.querySelectorAll( '.labwiki-sidebar-shell' ) ).forEach( function ( shell ) {
      var parent = shell.parentElement;

      if ( !parent || activeTargets.indexOf( parent ) !== -1 ) {
        return;
      }

      shell.remove();
    } );
  }

  function mountKnowledgeTree() {
    var sourceMenu = document.querySelector( '#vector-main-menu' );
    var targets;

    if ( document.body.classList.contains( 'mw-special-Userlogin' ) ||
      document.body.classList.contains( 'mw-special-LabLogin' ) ||
      document.body.classList.contains( 'mw-special-StudentSignup' ) ||
      document.body.classList.contains( 'mw-special-LabAccountAdmin' ) ||
      document.body.classList.contains( 'mw-special-Badtitle' ) ) {
      return;
    }

    if ( !sourceMenu ) {
      return;
    }

    targets = resolveMountTargets();
    clearInactiveKnowledgeTreeShells( targets );
    targets.forEach( function ( target ) {
      mountKnowledgeTreeInto( sourceMenu, target );
    } );
  }

  function mountAppearanceSettingsShortcut() {
    var label = document.querySelector( '#vector-appearance-dropdown-label' );
    var checkbox = document.querySelector( '#vector-appearance-dropdown-checkbox' );
    var content = document.querySelector( '#vector-appearance-dropdown .vector-dropdown-content' );
    var navigate = function ( event ) {
      if ( event ) {
        event.preventDefault();
        event.stopPropagation();
      }
      window.location.assign( getAppearanceSettingsUrl() );
    };

    if ( !label ) {
      return;
    }

    label.classList.add( 'labwiki-appearance-settings-link' );
    label.setAttribute( 'role', 'link' );
    label.setAttribute( 'tabindex', '0' );
    label.setAttribute( 'title', '界面设置' );
    label.setAttribute( 'aria-label', '界面设置' );
    label.removeAttribute( 'aria-hidden' );

    if ( checkbox ) {
      checkbox.checked = false;
      checkbox.tabIndex = -1;
      checkbox.setAttribute( 'aria-hidden', 'true' );
    }

    if ( content ) {
      content.remove();
    }

    if ( label.getAttribute( 'data-labwiki-appearance-bound' ) === '1' ) {
      return;
    }

    label.setAttribute( 'data-labwiki-appearance-bound', '1' );
    label.addEventListener( 'click', navigate );
    label.addEventListener( 'keydown', function ( event ) {
      if ( event.key === 'Enter' || event.key === ' ' ) {
        navigate( event );
      }
    } );
  }

  function refreshInjectedUi() {
    removeLegacyAppearanceLinks();
    renameKnowledgeTreeTrigger();
    mountKnowledgeTree();
    mountAppearanceSettingsShortcut();
  }

  function scheduleInjectedUiRefresh() {
    if ( refreshPending ) {
      return;
    }

    refreshPending = true;
    if ( window.requestAnimationFrame ) {
      window.requestAnimationFrame( function () {
        refreshPending = false;
        refreshInjectedUi();
      } );
      return;
    }

    window.setTimeout( function () {
      refreshPending = false;
      refreshInjectedUi();
    }, 0 );
  }

  if ( document.readyState === 'loading' ) {
    document.addEventListener( 'DOMContentLoaded', function () {
      refreshInjectedUi();

      if ( window.MutationObserver ) {
        new MutationObserver( function () {
          scheduleInjectedUiRefresh();
        } ).observe( document.body, {
          childList: true,
          subtree: true
        } );
      }
    } );
  } else {
    refreshInjectedUi();

    if ( window.MutationObserver ) {
      new MutationObserver( function () {
        scheduleInjectedUiRefresh();
      } ).observe( document.body, {
        childList: true,
        subtree: true
      } );
    }
  }
}() );
