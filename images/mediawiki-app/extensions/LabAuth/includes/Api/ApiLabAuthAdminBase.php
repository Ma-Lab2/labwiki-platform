<?php

namespace MediaWiki\Extension\LabAuth\Api;

use MediaWiki\Api\ApiBase;

abstract class ApiLabAuthAdminBase extends ApiBase {
	protected function requireAdminPermission(): void {
		$this->checkUserRightsAny( 'manage-lab-accounts' );
	}

	public function mustBePosted() {
		return true;
	}

	public function needsToken() {
		return 'csrf';
	}
}
