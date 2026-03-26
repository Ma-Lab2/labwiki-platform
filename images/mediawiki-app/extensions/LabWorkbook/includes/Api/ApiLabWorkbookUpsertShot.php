<?php

namespace MediaWiki\Extension\LabWorkbook\Api;

use MediaWiki\Extension\LabWorkbook\WorkbookStore;
use Wikimedia\ParamValidator\ParamValidator;

class ApiLabWorkbookUpsertShot extends ApiLabWorkbookBase {
	public function execute() {
		$this->requireRegisteredUser();
		$params = $this->extractRequestParams();
		$result = WorkbookStore::upsertShotPage(
			(string)$params['slug'],
			(string)$params['sheet_key'],
			(int)$params['row_index'],
			$this->getUser()
		);

		$this->getResult()->addValue( null, 'labworkbookupsertshot', $result );
	}

	public function mustBePosted() {
		return true;
	}

	public function needsToken() {
		return 'csrf';
	}

	public function isWriteMode() {
		return true;
	}

	public function getAllowedParams() {
		return [
			'slug' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_REQUIRED => true
			],
			'sheet_key' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_REQUIRED => true
			],
			'row_index' => [
				ParamValidator::PARAM_TYPE => 'integer',
				ParamValidator::PARAM_REQUIRED => true
			]
		];
	}
}
