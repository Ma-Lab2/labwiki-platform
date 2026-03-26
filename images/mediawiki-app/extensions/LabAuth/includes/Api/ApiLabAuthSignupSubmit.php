<?php

namespace MediaWiki\Extension\LabAuth\Api;

use MediaWiki\Api\ApiBase;
use MediaWiki\Extension\LabAuth\RegistrationStore;
use Wikimedia\ParamValidator\ParamValidator;

class ApiLabAuthSignupSubmit extends ApiBase {
	public function execute() {
		$params = $this->extractRequestParams();
		$errors = RegistrationStore::validateSignupData( $params );
		if ( $errors ) {
			$this->dieWithError( implode( ' ', $errors ) );
		}

		$requestId = RegistrationStore::createSignupRequest( $params );
		$this->getResult()->addValue( null, 'labauthsignupsubmit', [
			'request_id' => $requestId,
			'status' => RegistrationStore::STATUS_PENDING
		] );
	}

	public function mustBePosted() {
		return true;
	}

	public function isWriteMode() {
		return true;
	}

	public function getAllowedParams() {
		return [
			'username' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_REQUIRED => true
			],
			'real_name' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_REQUIRED => true
			],
			'student_id' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_REQUIRED => true
			],
			'email' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_REQUIRED => true
			],
			'password' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_REQUIRED => true
			]
		];
	}
}
