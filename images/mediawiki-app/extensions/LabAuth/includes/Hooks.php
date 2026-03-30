<?php

namespace MediaWiki\Extension\LabAuth;

use MediaWiki\Output\OutputPage;
use MediaWiki\SpecialPage\SpecialPage;
use MediaWiki\Title\Title;
use Skin;

class Hooks {
	public static function onTitleReadWhitelist( $title, $user, &$whitelisted ) {
		if ( !RegistrationStore::isPrivateWiki() ) {
			return;
		}

		if ( $title->isSpecial( 'StudentSignup' ) || $title->isSpecial( 'LabLogin' ) ) {
			$whitelisted = true;
		}
	}

	public static function onBeforePageDisplay( OutputPage $out, Skin $skin ): void {
		if ( !RegistrationStore::isPrivateWiki() ) {
			return;
		}

		$title = $out->getTitle();
		if ( !$title ) {
			return;
		}

		$isNativeLogin = $title->isSpecial( 'Userlogin' );
		$isLabLogin = $title->isSpecial( 'LabLogin' );
		if ( !$isNativeLogin && !$isLabLogin ) {
			return;
		}

		// Redirect handling is intentionally centralized in SpecialPageBeforeExecute
		// to avoid mixed native/custom login content during late page rendering.
		$skin->getUser();
	}

	public static function onSpecialPageBeforeExecute( $special, $subPage ) {
		if ( !RegistrationStore::isPrivateWiki() ) {
			return true;
		}

		$name = $special->getName();
		if ( $name !== 'Userlogin' && $name !== 'LabLogin' ) {
			return true;
		}

		$request = $special->getRequest();
		$out = $special->getOutput();
		$user = $special->getUser();
		if ( $user && $user->isRegistered() ) {
			$returnTo = trim( (string)$request->getText( 'returnto' ) );
			$targetUrl = $returnTo !== ''
				? Title::newFromText( $returnTo )?->getLocalURL() ?? Title::newMainPage()->getLocalURL()
				: Title::newMainPage()->getLocalURL();
			$out->redirect( $targetUrl );
			return false;
		}

		if ( $name === 'Userlogin' ) {
			$query = $request->getValues();
			unset( $query['title'] );
			$out->redirect( SpecialPage::getTitleFor( 'LabLogin' )->getLocalURL( $query ) );
			return false;
		}

		return true;
	}

	public static function onLoadExtensionSchemaUpdates( $updater ) {
		$updater->addExtensionTable(
			'labauth_registration_requests',
			__DIR__ . '/../sql/labauth_registration_requests.sql'
		);
		$updater->addExtensionTable(
			'labauth_user_profiles',
			__DIR__ . '/../sql/labauth_user_profiles.sql'
		);
		$updater->addExtensionTable(
			'labauth_admin_events',
			__DIR__ . '/../sql/labauth_admin_events.sql'
		);
	}
}
