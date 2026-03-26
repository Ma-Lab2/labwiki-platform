<?php

namespace MediaWiki\Extension\LabAuth;

use Html;
use MediaWiki\SpecialPage\SpecialPage;

class SpecialLabAccountAdmin extends SpecialPage {
	public function __construct() {
		parent::__construct( 'LabAccountAdmin', 'manage-lab-accounts' );
	}

	public function execute( $subPage ): void {
		$this->setHeaders();
		$out = $this->getOutput();
		$out->setPageTitleMsg( $this->msg( 'labauth-admin' ) );
		$out->addModules( [ 'ext.labauth.admin' ] );
		$out->addModuleStyles( [ 'ext.labauth.admin' ] );
		$out->addHTML( Html::rawElement(
			'div',
			[
				'id' => 'labauth-admin-root',
				'class' => 'labauth-root-shell'
			],
			''
		) );
	}

	protected function getGroupName(): string {
		return 'labwiki';
	}
}
