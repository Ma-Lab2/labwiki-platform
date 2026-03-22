<?php

namespace MediaWiki\Extension\LabAssistant;

use MediaWiki\Context\RequestContext;
use OutputPage;
use Skin;

class Hooks {
	public static function onBeforePageDisplay( OutputPage $out, Skin $skin ): void {
		$title = $out->getTitle();
		if ( !$title || !$skin->getUser()->isRegistered() ) {
			return;
		}

		if ( $title->isSpecial( 'LabAssistant' ) || $title->isSpecial( 'LabAssistantAdmin' ) ) {
			return;
		}

		$out->addModules( [ 'ext.labassistant.shell' ] );
		$out->addJsConfigVars(
			'wgLabAssistant',
			ClientConfigBuilder::build(
				$skin->getUser(),
				$title,
				RequestContext::getMain()->getRequest(),
				'drawer'
			)
		);
	}
}
