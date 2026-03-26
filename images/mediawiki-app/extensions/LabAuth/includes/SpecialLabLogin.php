<?php

namespace MediaWiki\Extension\LabAuth;

use LoginHelper;
use MediaWiki\Auth\AuthManager;
use MediaWiki\Logger\LoggerFactory;
use MediaWiki\MainConfigNames;
use MediaWiki\MediaWikiServices;
use MediaWiki\SpecialPage\LoginSignupSpecialPage;
use MediaWiki\SpecialPage\SpecialPage;
use StatusValue;

class SpecialLabLogin extends LoginSignupSpecialPage {
	protected static $allowedActions = [
		AuthManager::ACTION_LOGIN,
		AuthManager::ACTION_LOGIN_CONTINUE
	];

	protected static $messages = [
		'authform-newtoken' => 'nocookiesforlogin',
		'authform-notoken' => 'sessionfailure',
		'authform-wrongtoken' => 'sessionfailure',
	];

	public function __construct() {
		parent::__construct( 'LabLogin' );
		$this->setAuthManager( MediaWikiServices::getInstance()->getAuthManager() );
	}

	public function doesWrites() {
		return true;
	}

	public function isListed() {
		return $this->getAuthManager()->canAuthenticateNow();
	}

	protected function getLoginSecurityLevel() {
		return false;
	}

	protected function getDefaultAction( $subPage ) {
		return AuthManager::ACTION_LOGIN;
	}

	public function getDescription() {
		return $this->msg( 'labauth-login' );
	}

	public function setHeaders() {
		parent::setHeaders();
		$this->getOutput()->setPageTitleMsg( $this->msg( 'labauth-login' ) );
	}

	protected function isSignup() {
		return false;
	}

	protected function beforeExecute( $subPage ) {
		if ( $subPage === 'signup' || $this->getRequest()->getText( 'type' ) === 'signup' ) {
			$this->getOutput()->redirect( SpecialPage::getTitleFor( 'StudentSignup' )->getFullURL() );
			return false;
		}
		return parent::beforeExecute( $subPage );
	}

	protected function successfulAction( $direct = false, $extraMessages = null ) {
		$secureLogin = $this->getConfig()->get( MainConfigNames::SecureLogin );

		$user = $this->targetUser ?: $this->getUser();
		$session = $this->getRequest()->getSession();

		$injectedHtml = '';
		if ( $direct ) {
			$user->touch();
			$this->clearToken();

			if ( $user->requiresHTTPS() ) {
				$this->mStickHTTPS = true;
			}
			$session->setForceHTTPS( $secureLogin && $this->mStickHTTPS );

			if ( !$this->hasSessionCookie() ) {
				$this->mainLoginForm( [], $session->getProvider()->whyNoSession() );
				return;
			}

			$this->getHookRunner()->onUserLoginComplete( $user, $injectedHtml, $direct );
		}

		if ( $injectedHtml !== '' || $extraMessages ) {
			$this->showSuccessPage(
				'success',
				$this->msg( 'loginsuccesstitle' ),
				'loginsuccess',
				$injectedHtml,
				$extraMessages
			);
		} else {
			$helper = new LoginHelper( $this->getContext() );
			$helper->showReturnToPage(
				'successredirect',
				$this->mReturnTo,
				$this->mReturnToQuery,
				$this->mStickHTTPS,
				$this->mReturnToAnchor
			);
		}
	}

	protected function getToken() {
		return $this->getRequest()->getSession()->getToken( '', 'login' );
	}

	protected function clearToken() {
		$this->getRequest()->getSession()->resetToken( 'login' );
	}

	protected function getTokenName() {
		return 'wpLoginToken';
	}

	protected function getGroupName(): string {
		return 'labwiki';
	}

	protected function logAuthResult( $success, $status = null ) {
		LoggerFactory::getInstance( 'authevents' )->info( 'Lab login attempt', [
			'event' => 'lab-login',
			'successful' => $success,
			'status' => strval( $status ),
		] );
	}

	protected function getPageHtml( $formHtml ) {
		$out = $this->getOutput();
		$out->addModules( [ 'ext.labauth.login' ] );
		$out->addModuleStyles( [ 'ext.labauth.login' ] );

		$noticeHtml = '';
		if ( $this->getRequest()->getVal( 'labauthnotice' ) === 'disabled' ) {
			$noticeHtml = '<div class="labauth-banner is-warning">该账户已被管理员停用，请联系管理员。</div>';
		}

		$signupUrl = SpecialPage::getTitleFor( 'StudentSignup' )->getLocalURL();
		return '<div class="labauth-login-shell">'
			. '<div class="labauth-auth-card">'
			. '<div class="labauth-auth-header">'
			. '<small>Private Wiki</small>'
			. '<h1>' . $this->msg( 'labauth-login' )->escaped() . '</h1>'
			. '<p>使用实验室账号进入私有知识库。学生首次使用请先提交注册申请。</p>'
			. '</div>'
			. $noticeHtml
			. '<div class="labauth-login-form">' . $formHtml . '</div>'
			. '<div class="labauth-auth-footer">'
			. '<span>还没有账号？</span>'
			. '<a class="labauth-link" href="' . htmlspecialchars( $signupUrl ) . '">前往学生注册</a>'
			. '</div>'
			. '</div>'
			. '</div>';
	}
}
