<?php

namespace MediaWiki\Extension\LabAuth;

use MediaWiki\Auth\AbstractPreAuthenticationProvider;
use MediaWiki\Auth\AuthenticationRequest;
use MediaWiki\User\User;
use StatusValue;

class DisabledAccountPreAuthenticationProvider extends AbstractPreAuthenticationProvider {
	public function testForAuthentication( array $reqs ) {
		try {
			$username = AuthenticationRequest::getUsernameFromRequests( $reqs );
		} catch ( \UnexpectedValueException $exception ) {
			return StatusValue::newGood();
		}

		$user = User::newFromName( $username, 'usable' );
		if ( !$user || !$user->isRegistered() ) {
			return StatusValue::newGood();
		}

		if ( RegistrationStore::isUserDisabled( $user ) ) {
			return StatusValue::newFatal( '该账户已被管理员停用。' );
		}

		return StatusValue::newGood();
	}
}
