<?php

namespace MediaWiki\Extension\LabAuth;

use Html;
use MediaWiki\SpecialPage\SpecialPage;

class SpecialStudentSignup extends SpecialPage {
	public function __construct() {
		parent::__construct( 'StudentSignup', 'read' );
	}

	public function execute( $subPage ): void {
		$this->setHeaders();
		$out = $this->getOutput();
		$out->setPageTitleMsg( $this->msg( 'labauth-signup' ) );
		$out->addModuleStyles( [ 'ext.labauth.signup' ] );
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

		$loginUrl = SpecialPage::getTitleFor( 'Userlogin' )->getLocalURL();
		$formChildren = [];
		if ( !$formHidden ) {
			$formChildren[] = $this->buildField( 'real_name', '姓名', $fields['real_name'] );
			$formChildren[] = $this->buildField( 'student_id', '学号', $fields['student_id'] );
			$formChildren[] = $this->buildField( 'email', '邮箱', $fields['email'], 'email' );
			$formChildren[] = $this->buildField( 'username', '用户名', $fields['username'] );
			$formChildren[] = $this->buildField( 'password', '密码', '', 'password' );
			$formChildren[] = Html::element(
				'button',
				[
					'type' => 'submit',
					'class' => 'labauth-button-primary'
				],
				'提交注册申请'
			);
		}

		$out->addHTML(
			Html::rawElement( 'div', [ 'class' => 'labauth-login-shell' ], Html::rawElement(
				'section',
				[ 'class' => 'labauth-auth-card' ],
				Html::rawElement( 'div', [ 'class' => 'labauth-auth-header' ],
					Html::element( 'small', [], 'Student Access' ) .
					Html::element( 'h1', [], '学生注册' ) .
					Html::element( 'p', [], '提交姓名、学号、邮箱和登录用户名。管理员审核通过后才会开通账号。' )
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
					Html::element( 'span', [], '已经有账号？' ) .
					Html::element( 'a', [ 'class' => 'labauth-link', 'href' => $loginUrl ], '返回登录' )
				)
			) )
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
