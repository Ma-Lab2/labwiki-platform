<?php

namespace MediaWiki\Extension\LabAssistant;

use Html;
use MediaWiki\SpecialPage\SpecialPage;
use OutputPage;
use Skin;

class SpecialLabAssistant extends SpecialPage {
	public function __construct() {
		parent::__construct( 'LabAssistant', 'read' );
	}

	public function execute( $subPage ): void {
		$this->setHeaders();

		$out = $this->getOutput();
		$user = $this->getUser();
		$request = $this->getRequest();

		$out->setPageTitle( $this->msg( 'labassistant' ) );
		$out->addModules( [ 'ext.labassistant.ui' ] );
		$out->addModuleStyles( [ 'ext.labassistant.ui' ] );
		$out->addJsConfigVars( 'wgLabAssistant', [
			'apiBase' => $GLOBALS['wgLabAssistantApiBase'] ?? '/tools/assistant/api',
			'draftPrefix' => $GLOBALS['wgLabAssistantDraftPrefix'] ?? '知识助手草稿',
			'modes' => $GLOBALS['wgLabAssistantModes'] ?? [ 'qa', 'compare', 'draft' ],
			'detailLevels' => $GLOBALS['wgLabAssistantDetailLevels'] ?? [ 'intro', 'intermediate', 'research' ],
			'userName' => $user->isRegistered() ? $user->getName() : null,
			'currentTitle' => $this->getContext()->getTitle()->getPrefixedText(),
			'seedQuestion' => trim( (string)$request->getVal( 'q', '' ) ),
		] );

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

