<?php

namespace MediaWiki\Extension\LabAuth\Api;

use MediaWiki\Extension\LabAuth\RegistrationStore;
use Wikimedia\ParamValidator\ParamValidator;

class ApiLabAuthAdminApprove extends ApiLabAuthAdminBase {
	public function execute() {
		$this->requireAdminPermission();
		$params = $this->extractRequestParams();

		try {
			$result = RegistrationStore::approveSignupRequest(
				(int)$params['request_id'],
				$this->getUser(),
				(string)$params['review_note']
			);
		} catch ( \RuntimeException $exception ) {
			$this->dieWithError( $exception->getMessage() );
		}

		$this->getResult()->addValue( null, 'labauthadminapprove', $result );
	}

	public function getAllowedParams() {
		return [
			'request_id' => [
				ParamValidator::PARAM_TYPE => 'integer',
				ParamValidator::PARAM_REQUIRED => true
			],
			'review_note' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_DEFAULT => ''
			]
		];
	}
}
