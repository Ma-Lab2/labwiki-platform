<?php

namespace MediaWiki\Extension\LabAuth\Api;

use MediaWiki\Extension\LabAuth\RegistrationStore;

class ApiLabAuthAdminQueue extends ApiLabAuthAdminBase {
	public function execute() {
		$this->requireAdminPermission();
		$this->getResult()->addValue( null, 'labauthadminqueue', [
			'requests' => RegistrationStore::getPendingRequests()
		] );
	}

	public function mustBePosted() {
		return false;
	}

	public function needsToken() {
		return false;
	}
}
