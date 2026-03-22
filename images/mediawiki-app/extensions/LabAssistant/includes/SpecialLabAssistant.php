<?php

namespace MediaWiki\Extension\LabAssistant;

use Html;
use MediaWiki\SpecialPage\SpecialPage;

class SpecialLabAssistant extends SpecialPage {
	public function __construct() {
		parent::__construct( 'LabAssistant', 'read' );
	}

	public function execute( $subPage ): void {
		$this->setHeaders();

		$out = $this->getOutput();
		$user = $this->getUser();
		$request = $this->getRequest();

		$out->setPageTitleMsg( $this->msg( 'labassistant' ) );
		$out->addModules( [ 'ext.labassistant.shell' ] );
		$out->addJsConfigVars(
			'wgLabAssistant',
			ClientConfigBuilder::build(
				$user,
				$this->getContext()->getTitle(),
				$request,
				'special'
			)
		);

		$out->addHTML( Html::rawElement(
			'div',
			[
				'id' => 'labassistant-root',
				'class' => 'labassistant-root-shell'
			],
			''
		) );
	}

	protected function getGroupName(): string {
		return 'labwiki';
	}
}
