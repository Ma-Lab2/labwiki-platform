<?php

namespace MediaWiki\Extension\LabAuth\Api;

use MediaWiki\Extension\LabAuth\RegistrationStore;

class ApiLabAuthAdminActivity extends ApiLabAuthAdminBase {
	public function execute() {
		$this->requireAdminPermission();
		$this->getResult()->addValue( null, 'labauthadminactivity', [
			'events' => RegistrationStore::getAdminEvents()
		] );
	}

	public function mustBePosted() {
		return false;
	}

	public function needsToken() {
		return false;
	}
}
