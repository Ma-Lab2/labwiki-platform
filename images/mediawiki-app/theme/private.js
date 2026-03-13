( function () {
  function stripIds( node ) {
    if ( node.nodeType !== Node.ELEMENT_NODE ) {
      return;
    }
    node.removeAttribute( 'id' );
    node.querySelectorAll( '[id]' ).forEach( function ( child ) {
      child.removeAttribute( 'id' );
    } );
  }

  function mountKnowledgeTree() {
    if ( document.body.classList.contains( 'mw-special-Userlogin' ) ||
      document.body.classList.contains( 'mw-special-Badtitle' ) ) {
      return;
    }

    var sourceMenu = document.querySelector( '#vector-main-menu' );
    var target = document.querySelector( '#vector-main-menu-pinned-container' );

    if ( !sourceMenu || !target || target.querySelector( '.labwiki-sidebar-shell' ) ) {
      return;
    }

    var wrapper = document.createElement( 'div' );
    wrapper.className = 'labwiki-sidebar-shell';
    wrapper.innerHTML =
      '<div class="labwiki-sidebar-header">' +
      '<small>Knowledge Tree</small>' +
      '<strong>课题组知识树</strong>' +
      '</div>';

    Array.prototype.slice.call( sourceMenu.querySelectorAll( '.vector-menu.mw-portlet' ) ).forEach( function ( menu ) {
      var clone = menu.cloneNode( true );
      stripIds( clone );
      wrapper.appendChild( clone );
    } );

    target.appendChild( wrapper );
  }

  if ( document.readyState === 'loading' ) {
    document.addEventListener( 'DOMContentLoaded', mountKnowledgeTree );
  } else {
    mountKnowledgeTree();
  }
}() );
