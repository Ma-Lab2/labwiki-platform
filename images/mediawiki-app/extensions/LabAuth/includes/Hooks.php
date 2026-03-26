<?php

namespace MediaWiki\Extension\LabAuth;

class Hooks {
	public static function onTitleReadWhitelist( $title, $user, &$whitelisted ) {
		if ( !RegistrationStore::isPrivateWiki() ) {
			return;
		}

		if ( $title->isSpecial( 'StudentSignup' ) ) {
			$whitelisted = true;
		}
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
