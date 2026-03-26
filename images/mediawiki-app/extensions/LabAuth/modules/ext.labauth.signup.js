( function () {
  function el( tag, attrs, children ) {
    var node = document.createElement( tag );
    Object.entries( attrs || {} ).forEach( function ( entry ) {
      if ( entry[ 0 ] === 'className' ) {
        node.className = entry[ 1 ];
      } else if ( entry[ 0 ] === 'text' ) {
        node.textContent = entry[ 1 ];
      } else if ( entry[ 0 ] === 'html' ) {
        node.innerHTML = entry[ 1 ];
      } else if ( entry[ 0 ] === 'for' ) {
        node.htmlFor = entry[ 1 ];
      } else {
        node.setAttribute( entry[ 0 ], entry[ 1 ] );
      }
    } );
    ( children || [] ).forEach( function ( child ) {
      node.appendChild( child );
    } );
    return node;
  }

  function createField( id, label, type ) {
    var input = el( 'input', {
      id: id,
      name: id,
      type: type || 'text',
      className: 'labauth-input',
      autocomplete: 'off'
    } );

    return {
      wrapper: el( 'div', { className: 'labauth-field' }, [
        el( 'label', { for: id, text: label } ),
        input
      ] ),
      input: input
    };
  }

  function mountSignup() {
    var root = document.getElementById( 'labauth-signup-root' );
    if ( !root || !window.mw ) {
      return;
    }

    var api = new mw.Api();
    var loginUrl = mw.util.getUrl( 'Special:用户登录' );
    var card = el( 'section', { className: 'labauth-auth-card' } );
    var status = el( 'div', { className: 'labauth-status', hidden: 'hidden' } );
    var form = el( 'form', { className: 'labauth-form' } );

    var realName = createField( 'real_name', '姓名' );
    var studentId = createField( 'student_id', '学号' );
    var email = createField( 'email', '邮箱', 'email' );
    var username = createField( 'username', '用户名' );
    var password = createField( 'password', '密码', 'password' );
    password.input.autocomplete = 'new-password';

    [
      realName.wrapper,
      studentId.wrapper,
      email.wrapper,
      username.wrapper,
      password.wrapper
    ].forEach( function ( field ) {
      form.appendChild( field );
    } );

    var submitButton = el( 'button', {
      type: 'submit',
      className: 'labauth-button-primary',
      text: '提交注册申请'
    } );
    form.appendChild( submitButton );

    function setStatus( type, message ) {
      status.hidden = false;
      status.className = 'labauth-status is-' + type;
      status.textContent = message;
    }

    form.addEventListener( 'submit', function ( event ) {
      event.preventDefault();
      submitButton.disabled = true;
      status.hidden = true;

      api.postWithToken( 'csrf', {
        action: 'labauthsignupsubmit',
        format: 'json',
        real_name: realName.input.value.trim(),
        student_id: studentId.input.value.trim(),
        email: email.input.value.trim(),
        username: username.input.value.trim(),
        password: password.input.value
      } ).then( function ( response ) {
        var payload = response && response.labauthsignupsubmit;
        if ( !payload ) {
          throw new Error( '注册响应不完整。' );
        }
        form.hidden = true;
        setStatus( 'success', '注册申请已提交，等待管理员审核。申请编号：' + payload.request_id );
      } ).catch( function ( error ) {
        setStatus( 'error', error && error.message ? error.message : '注册申请提交失败。' );
      } ).finally( function () {
        submitButton.disabled = false;
      } );
    } );

    card.appendChild( el( 'div', { className: 'labauth-auth-header' }, [
      el( 'small', { text: 'Student Access' } ),
      el( 'h1', { text: '学生注册' } ),
      el( 'p', { text: '提交姓名、学号、邮箱和登录用户名。管理员审核通过后才会开通账号。' } )
    ] ) );
    card.appendChild( status );
    card.appendChild( form );
    card.appendChild( el( 'div', { className: 'labauth-auth-footer' }, [
      el( 'span', { text: '已经有账号？' } ),
      el( 'a', { className: 'labauth-link', href: loginUrl, text: '返回登录' } )
    ] ) );

    root.appendChild( el( 'div', { className: 'labauth-login-shell' }, [ card ] ) );
  }

  if ( document.readyState === 'loading' ) {
    document.addEventListener( 'DOMContentLoaded', mountSignup );
  } else {
    mountSignup();
  }
}() );
