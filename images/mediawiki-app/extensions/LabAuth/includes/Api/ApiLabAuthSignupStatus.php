<?php

namespace MediaWiki\Extension\LabAuth\Api;

use MediaWiki\Api\ApiBase;
use MediaWiki\Extension\LabAuth\RegistrationStore;
use Wikimedia\ParamValidator\ParamValidator;

class ApiLabAuthSignupStatus extends ApiBase {
	public function execute() {
		$params = $this->extractRequestParams();
		$status = RegistrationStore::getSignupRequestStatus( (int)$params['request_id'] );
		if ( !$status ) {
			$this->dieWithError( '注册申请不存在。' );
		}
		$this->getResult()->addValue( null, 'labauthsignupstatus', $status );
	}

	public function getAllowedParams() {
		return [
			'request_id' => [
				ParamValidator::PARAM_TYPE => 'integer',
				ParamValidator::PARAM_REQUIRED => true
			]
		];
	}
}
