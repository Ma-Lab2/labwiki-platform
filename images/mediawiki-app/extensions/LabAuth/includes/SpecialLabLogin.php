<?php

namespace MediaWiki\Extension\LabAuth;

use LoginHelper;
use MediaWiki\Auth\AuthManager;
use MediaWiki\Logger\LoggerFactory;
use MediaWiki\MainConfigNames;
use MediaWiki\MediaWikiServices;
use MediaWiki\SpecialPage\LoginSignupSpecialPage;
use MediaWiki\SpecialPage\SpecialPage;
use MediaWiki\Title\Title;
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
		if ( $this->getUser()->isRegistered() ) {
			$this->getOutput()->redirect( Title::newMainPage()->getLocalURL() );
			return false;
		}

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
		$homeUrl = Title::newMainPage()->getLocalURL();
		return '<div class="labauth-login-shell">'
			. '<section class="labauth-portal-shell">'
			. '<aside class="labauth-portal-hero">'
			. '<div class="labauth-auth-header">'
			. '<small>Private Wiki</small>'
			. '<h1>' . $this->msg( 'labauth-login' )->escaped() . '</h1>'
			. '<p>进入实验运行台账、控制文档和知识整理工作区。学生首次使用请先提交注册申请。</p>'
			. '</div>'
			. '<div class="labauth-hero-steps">'
			. '<div class="labauth-hero-step"><strong>实验资料集中管理</strong><span>统一访问私有知识库、记录页和控制文档。</span></div>'
			. '<div class="labauth-hero-step"><strong>学生账号需审核</strong><span>学生先注册，管理员审核通过后才能登录。</span></div>'
			. '<div class="labauth-hero-step"><strong>管理员统一维护</strong><span>账户停用、恢复和审计记录都在后台完成。</span></div>'
			. '</div>'
			. '<div class="labauth-hero-meta">'
			. '<span>仅面向课题组内部成员开放。</span>'
			. '<span>如遇停用提示，请联系管理员。</span>'
			. '</div>'
			. '</aside>'
			. '<section class="labauth-auth-card labauth-auth-card-form">'
			. '<div class="labauth-auth-header">'
			. '<small>Account Login</small>'
			. '<h2>' . $this->msg( 'labauth-login' )->escaped() . '</h2>'
			. '<p>使用已开通的实验室账号登录私有 Wiki。</p>'
			. '</div>'
			. $noticeHtml
			. '<div class="labauth-login-form">' . $formHtml . '</div>'
			. '<div class="labauth-auth-footer">'
			. '<a class="labauth-link-button" href="' . htmlspecialchars( $homeUrl ) . '">返回首页</a>'
			. '<div class="labauth-inline-links">'
			. '<span>还没有账号？</span>'
			. '<a class="labauth-link" href="' . htmlspecialchars( $signupUrl ) . '">前往学生注册</a>'
			. '</div>'
			. '</div>'
			. '</section>'
			. '</section>'
			. '</div>';
	}
}
