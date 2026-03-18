<?php

namespace MediaWiki\Extension\LabAssistant;

use Html;
use MediaWiki\SpecialPage\SpecialPage;

class SpecialLabAssistantAdmin extends SpecialPage {
	public function __construct() {
		parent::__construct( 'LabAssistantAdmin', 'editinterface' );
	}

	public function execute( $subPage ): void {
		$this->setHeaders();

		$out = $this->getOutput();
		$out->setPageTitle( $this->msg( 'labassistantadmin' ) );
		$out->addModules( [ 'ext.labassistant.admin' ] );
		$out->addModuleStyles( [ 'ext.labassistant.ui' ] );
		$out->addJsConfigVars( 'wgLabAssistantAdmin', [
			'apiBase' => $GLOBALS['wgLabAssistantApiBase'] ?? '/tools/assistant/api',
		] );

		$out->addHTML( Html::rawElement(
			'div',
			[
				'id' => 'labassistant-admin-root',
				'class' => 'labassistant-root-shell'
			],
			''
		) );
	}

	protected function getGroupName(): string {
		return 'labwiki';
	}
}

