<?php

namespace MediaWiki\Extension\LabAuth\Api;

use MediaWiki\Extension\LabAuth\RegistrationStore;

class ApiLabAuthAdminUsers extends ApiLabAuthAdminBase {
	public function execute() {
		$this->requireAdminPermission();
		$this->getResult()->addValue( null, 'labauthadminusers', [
			'users' => RegistrationStore::getManagedUsers()
		] );
	}

	public function mustBePosted() {
		return false;
	}

	public function needsToken() {
		return false;
	}
}
