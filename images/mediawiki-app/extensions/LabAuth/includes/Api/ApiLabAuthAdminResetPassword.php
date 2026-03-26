<?php

namespace MediaWiki\Extension\LabAuth\Api;

use MediaWiki\Extension\LabAuth\RegistrationStore;
use Wikimedia\ParamValidator\ParamValidator;

class ApiLabAuthAdminResetPassword extends ApiLabAuthAdminBase {
	public function execute() {
		$this->requireAdminPermission();
		$params = $this->extractRequestParams();
		try {
			RegistrationStore::resetPassword(
				(int)$params['user_id'],
				(string)$params['new_password'],
				$this->getUser()
			);
		} catch ( \RuntimeException $exception ) {
			$this->dieWithError( $exception->getMessage() );
		}

		$this->getResult()->addValue( null, 'labauthadminresetpassword', [
			'user_id' => (int)$params['user_id'],
			'password_reset' => true
		] );
	}

	public function getAllowedParams() {
		return [
			'user_id' => [
				ParamValidator::PARAM_TYPE => 'integer',
				ParamValidator::PARAM_REQUIRED => true
			],
			'new_password' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_REQUIRED => true
			]
		];
	}
}
