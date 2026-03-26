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

		$assetEpoch = (string)( $GLOBALS['wgLabAssistantAssetEpoch'] ?? '2026-03-25-pdf-ingest-1' );
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
		$out->addJsConfigVars( 'wgLabAssistantAssetEpoch', $assetEpoch );
		$out->addInlineScript( self::buildAssetEpochBootstrap( $assetEpoch ) );
	}

	private static function buildAssetEpochBootstrap( string $assetEpoch ): string {
		$storeKey = 'MediaWikiModuleStore:' . ( $GLOBALS['wgDBname'] ?? 'labwiki' );
		$epochKey = 'labassistant-asset-epoch::' . ( $GLOBALS['wgDBname'] ?? 'labwiki' );

		return sprintf(
			'(function(){try{if(!window.localStorage){return;}var epoch=%s;var epochKey=%s;var storeKey=%s;var previousEpoch=localStorage.getItem(epochKey);if(previousEpoch===epoch){return;}localStorage.removeItem(storeKey);localStorage.setItem(epochKey,epoch);}catch(e){}}());',
			json_encode( $assetEpoch, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES ),
			json_encode( $epochKey, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES ),
			json_encode( $storeKey, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES )
		);
	}
}
