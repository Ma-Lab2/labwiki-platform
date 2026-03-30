<?php

namespace MediaWiki\Extension\LabAuth;

use Html;
use MediaWiki\SpecialPage\SpecialPage;
use MediaWiki\Title\Title;

class SpecialStudentSignup extends SpecialPage {
	public function __construct() {
		parent::__construct( 'StudentSignup', 'read' );
	}

	public function execute( $subPage ): void {
		$this->setHeaders();
		$out = $this->getOutput();
		$out->setPageTitleMsg( $this->msg( 'labauth-signup' ) );
		$out->addModuleStyles( [ 'ext.labauth.signup' ] );
		if ( $this->getUser()->isRegistered() ) {
			$out->redirect( Title::newMainPage()->getLocalURL() );
			return;
		}

		$request = $this->getRequest();
		$statusHtml = '';
		$formHidden = false;
		$fields = [
			'real_name' => trim( (string)$request->getText( 'real_name' ) ),
			'student_id' => trim( (string)$request->getText( 'student_id' ) ),
			'email' => trim( (string)$request->getText( 'email' ) ),
			'username' => trim( (string)$request->getText( 'username' ) ),
			'password' => ''
		];

		if ( $request->wasPosted() ) {
			$fields['password'] = (string)$request->getVal( 'password' );
			$errors = RegistrationStore::validateSignupData( $fields );
			if ( $errors ) {
				$statusHtml = Html::element(
					'div',
					[ 'class' => 'labauth-status is-error' ],
					implode( ' ', $errors )
				);
			} else {
				$requestId = RegistrationStore::createSignupRequest( $fields );
				$statusHtml = Html::element(
					'div',
					[ 'class' => 'labauth-status is-success' ],
					'注册申请已提交，等待管理员审核。申请编号：' . $requestId
				);
				$formHidden = true;
			}
		}

		$loginUrl = SpecialPage::getTitleFor( 'LabLogin' )->getLocalURL();
		$homeUrl = Title::newMainPage()->getLocalURL();
		$formChildren = [];
		if ( !$formHidden ) {
			$formChildren[] = Html::rawElement(
				'div',
				[ 'class' => 'labauth-field-grid' ],
				$this->buildField( 'real_name', '姓名', $fields['real_name'] ) .
				$this->buildField( 'student_id', '学号', $fields['student_id'] )
			);
			$formChildren[] = Html::rawElement(
				'div',
				[ 'class' => 'labauth-field-grid' ],
				$this->buildField( 'email', '邮箱', $fields['email'], 'email' ) .
				$this->buildField( 'username', '用户名', $fields['username'] )
			);
			$formChildren[] = $this->buildField( 'password', '密码', '', 'password' );
			$formChildren[] = Html::rawElement(
				'div',
				[ 'class' => 'labauth-form-actions' ],
				Html::element(
					'button',
					[
						'type' => 'submit',
						'class' => 'labauth-button-primary'
					],
					'提交注册申请'
				)
			);
		}

		$out->addHTML(
			Html::rawElement( 'div', [ 'class' => 'labauth-login-shell' ],
				Html::rawElement( 'section', [ 'class' => 'labauth-portal-shell' ],
					Html::rawElement( 'aside', [ 'class' => 'labauth-portal-hero' ],
						Html::rawElement( 'div', [ 'class' => 'labauth-auth-header' ],
							Html::element( 'small', [], 'Student Access' ) .
							Html::element( 'h1', [], '学生注册' ) .
							Html::element( 'p', [], '先提交注册申请，再等待管理员审核。审核通过后，学生账号才能进入私有知识库。' )
						) .
						Html::rawElement( 'div', [ 'class' => 'labauth-hero-steps' ],
							Html::rawElement( 'div', [ 'class' => 'labauth-hero-step' ],
								Html::element( 'strong', [], '1. 提交申请' ) .
								Html::element( 'span', [], '填写姓名、学号、邮箱和用户名。' )
							) .
							Html::rawElement( 'div', [ 'class' => 'labauth-hero-step' ],
								Html::element( 'strong', [], '2. 管理员审核' ) .
								Html::element( 'span', [], '审核通过后才会正式开通账号。' )
							) .
							Html::rawElement( 'div', [ 'class' => 'labauth-hero-step' ],
								Html::element( 'strong', [], '3. 登录使用' ) .
								Html::element( 'span', [], '账号开通后再从实验室登录页进入系统。' )
							)
						) .
						Html::rawElement( 'div', [ 'class' => 'labauth-hero-meta' ],
							Html::element( 'span', [], '用于实验运行台账、知识库与资料整理。' ) .
							Html::element( 'span', [], '注册申请仅对课题组内部成员开放。' )
						)
					) .
					Html::rawElement( 'section', [ 'class' => 'labauth-auth-card labauth-auth-card-form' ],
						Html::rawElement( 'div', [ 'class' => 'labauth-auth-header' ],
							Html::element( 'small', [], 'Registration Form' ) .
							Html::element( 'h2', [], '提交学生注册申请' ) .
							Html::element( 'p', [], '这一步只会创建待审核申请，不会直接开通账号。' )
						) .
						$statusHtml .
						Html::rawElement(
							'form',
							[
								'class' => 'labauth-form',
								'method' => 'post',
								'action' => $request->getRequestURL()
							],
							implode( '', $formChildren )
						) .
						Html::rawElement( 'div', [ 'class' => 'labauth-auth-footer' ],
							Html::element( 'a', [ 'class' => 'labauth-link-button', 'href' => $homeUrl ], '返回首页' ) .
							Html::rawElement( 'div', [ 'class' => 'labauth-inline-links' ],
								Html::element( 'span', [], '已经有账号？' ) .
								Html::element( 'a', [ 'class' => 'labauth-link', 'href' => $loginUrl ], '返回登录' )
							)
						)
					)
				)
			)
		);
	}

	private function buildField( string $name, string $label, string $value, string $type = 'text' ): string {
		$inputAttributes = [
			'id' => $name,
			'name' => $name,
			'type' => $type,
			'class' => 'labauth-input',
			'autocomplete' => $type === 'password' ? 'new-password' : 'off'
		];
		if ( $type !== 'password' ) {
			$inputAttributes['value'] = $value;
		}

		return Html::rawElement(
			'div',
			[ 'class' => 'labauth-field' ],
			Html::label( $label, $name ) .
			Html::input( $name, $type === 'password' ? '' : $value, $type, $inputAttributes )
		);
	}

	protected function getGroupName(): string {
		return 'labwiki';
	}
}
