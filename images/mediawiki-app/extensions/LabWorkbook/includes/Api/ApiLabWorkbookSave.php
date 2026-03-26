<?php

namespace MediaWiki\Extension\LabWorkbook\Api;

use MediaWiki\Extension\LabWorkbook\WorkbookStore;
use Wikimedia\ParamValidator\ParamValidator;

class ApiLabWorkbookSave extends ApiLabWorkbookBase {
	public function execute() {
		$this->requireRegisteredUser();
		$params = $this->extractRequestParams();
		$updated = WorkbookStore::saveWorkbookChanges(
			(string)$params['slug'],
			[
				'run_label' => $params['run_label'],
				'sheet_key' => $params['sheet_key'],
				'sheet_data' => $params['sheet_data']
			]
		);

		$this->getResult()->addValue( null, 'labworkbooksave', [
			'workbook' => $updated
		] );
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
			'run_label' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_REQUIRED => false
			],
			'sheet_key' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_REQUIRED => false
			],
			'sheet_data' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_REQUIRED => false
			]
		];
	}
}
