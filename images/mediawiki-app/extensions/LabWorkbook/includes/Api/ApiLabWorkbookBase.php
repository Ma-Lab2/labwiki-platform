<?php

namespace MediaWiki\Extension\LabWorkbook\Api;

use MediaWiki\Api\ApiBase;

abstract class ApiLabWorkbookBase extends ApiBase {
	protected function requireRegisteredUser(): void {
		if ( !$this->getUser()->isRegistered() ) {
			$this->dieWithError( '必须登录后才能使用实验工作簿。' );
		}
	}
}
