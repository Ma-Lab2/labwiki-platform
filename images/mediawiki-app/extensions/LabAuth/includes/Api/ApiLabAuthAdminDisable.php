<?php

namespace MediaWiki\Extension\LabAuth\Api;

use MediaWiki\Extension\LabAuth\RegistrationStore;
use Wikimedia\ParamValidator\ParamValidator;

class ApiLabAuthAdminDisable extends ApiLabAuthAdminBase {
	public function execute() {
		$this->requireAdminPermission();
		$params = $this->extractRequestParams();
		try {
			RegistrationStore::setAccountStatus(
				(int)$params['user_id'],
				RegistrationStore::ACCOUNT_DISABLED,
				$this->getUser()
			);
		} catch ( \RuntimeException $exception ) {
			$this->dieWithError( $exception->getMessage() );
		}

		$this->getResult()->addValue( null, 'labauthadmindisable', [
			'user_id' => (int)$params['user_id'],
			'account_status' => RegistrationStore::ACCOUNT_DISABLED
		] );
	}

	public function getAllowedParams() {
		return [
			'user_id' => [
				ParamValidator::PARAM_TYPE => 'integer',
				ParamValidator::PARAM_REQUIRED => true
			]
		];
	}
}
