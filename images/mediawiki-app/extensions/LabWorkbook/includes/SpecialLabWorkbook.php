<?php

namespace MediaWiki\Extension\LabWorkbook;

use Html;
use MediaWiki\SpecialPage\SpecialPage;

class SpecialLabWorkbook extends SpecialPage {
	public function __construct() {
		parent::__construct( 'LabWorkbook', 'read' );
	}

	public function execute( $subPage ): void {
		$this->setHeaders();

		$out = $this->getOutput();
		$out->setPageTitleMsg( $this->msg( 'labworkbook' ) );
		$out->addModules( [ 'ext.labworkbook.ui' ] );
		$out->addJsConfigVars( 'wgLabWorkbook', [
			'selectedSlug' => $subPage !== null ? trim( (string)$subPage ) : ''
		] );
		$out->addHTML( Html::rawElement(
			'div',
			[
				'id' => 'labworkbook-root',
				'class' => 'labworkbook-root'
			],
			''
		) );
	}

	protected function getGroupName(): string {
		return 'labwiki';
	}
}
