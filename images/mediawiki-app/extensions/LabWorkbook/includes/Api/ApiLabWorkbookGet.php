<?php

namespace MediaWiki\Extension\LabWorkbook\Api;

use MediaWiki\Extension\LabWorkbook\WorkbookStore;
use Wikimedia\ParamValidator\ParamValidator;

class ApiLabWorkbookGet extends ApiLabWorkbookBase {
	public function execute() {
		$this->requireRegisteredUser();
		$params = $this->extractRequestParams();
		$selectedSlug = trim( (string)( $params['slug'] ?? '' ) );
		$workbooks = WorkbookStore::getWorkbookSummaries();

		if ( $selectedSlug === '' && $workbooks ) {
			$selectedSlug = (string)$workbooks[0]['slug'];
		}

		$this->getResult()->addValue( null, 'labworkbookget', [
			'workbooks' => $workbooks,
			'selected_slug' => $selectedSlug,
			'workbook' => $selectedSlug !== '' ? WorkbookStore::getWorkbookBySlug( $selectedSlug ) : null
		] );
	}

	public function mustBePosted() {
		return false;
	}

	public function needsToken() {
		return false;
	}

	public function getAllowedParams() {
		return [
			'slug' => [
				ParamValidator::PARAM_TYPE => 'string',
				ParamValidator::PARAM_REQUIRED => false
			]
		];
	}
}
