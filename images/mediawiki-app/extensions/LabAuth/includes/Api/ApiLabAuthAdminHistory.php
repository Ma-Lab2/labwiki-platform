<?php

namespace MediaWiki\Extension\LabAuth\Api;

use MediaWiki\Extension\LabAuth\RegistrationStore;

class ApiLabAuthAdminHistory extends ApiLabAuthAdminBase {
	public function execute() {
		$this->requireAdminPermission();
		$this->getResult()->addValue( null, 'labauthadminhistory', [
			'requests' => RegistrationStore::getReviewedRequests()
		] );
	}

	public function mustBePosted() {
		return false;
	}

	public function needsToken() {
		return false;
	}
}
