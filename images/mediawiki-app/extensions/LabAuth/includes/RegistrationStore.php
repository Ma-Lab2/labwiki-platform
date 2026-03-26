<?php

namespace MediaWiki\Extension\LabAuth;

use MediaWiki\Auth\AuthenticationRequest;
use MediaWiki\Auth\AuthManager;
use MediaWiki\Auth\AuthenticationResponse;
use MediaWiki\MediaWikiServices;
use MediaWiki\SpecialPage\SpecialPage;
use RequestContext;
use MediaWiki\User\User;
use Wikimedia\Rdbms\IDatabase;
use Wikimedia\Rdbms\SelectQueryBuilder;

class RegistrationStore {
	public const STATUS_PENDING = 'pending';
	public const STATUS_APPROVED = 'approved';
	public const STATUS_REJECTED = 'rejected';
	public const STATUS_CANCELLED = 'cancelled';

	public const ACCOUNT_ACTIVE = 'active';
	public const ACCOUNT_DISABLED = 'disabled';

	private static function getDbw(): IDatabase {
		return MediaWikiServices::getInstance()->getConnectionProvider()->getPrimaryDatabase();
	}

	private static function getDbr(): IDatabase {
		return MediaWikiServices::getInstance()->getConnectionProvider()->getReplicaDatabase();
	}

	public static function isPrivateWiki(): bool {
		return strtolower( (string)( getenv( 'MW_PRIVATE_MODE' ) ?: '' ) ) === 'true';
	}

	public static function hashPassword( string $password ): string {
		return self::encryptPendingPassword( $password );
	}

	public static function validateSignupData( array $data ): array {
		$errors = [];
		$username = trim( (string)( $data['username'] ?? '' ) );
		$realName = trim( (string)( $data['real_name'] ?? '' ) );
		$studentId = trim( (string)( $data['student_id'] ?? '' ) );
		$email = trim( (string)( $data['email'] ?? '' ) );
		$password = (string)( $data['password'] ?? '' );

		$user = User::newFromName( $username, 'creatable' );
		if ( !$user ) {
			$errors[] = '用户名格式无效。';
		}
		if ( $realName === '' ) {
			$errors[] = '姓名不能为空。';
		}
		if ( $studentId === '' ) {
			$errors[] = '学号不能为空。';
		}
		if ( $email === '' || !filter_var( $email, FILTER_VALIDATE_EMAIL ) ) {
			$errors[] = '邮箱格式无效。';
		}
		if ( $password === '' ) {
			$errors[] = '密码不能为空。';
		} elseif ( $user ) {
			$status = $user->checkPasswordValidity( $password );
			if ( !$status->isGood() ) {
				$errors[] = $status->getMessage()->text();
			}
		}

		if ( self::userExists( $username ) ) {
			$errors[] = '用户名已存在。';
		}
		if ( self::pendingFieldExists( 'lr_username', $username ) ) {
			$errors[] = '该用户名已有待审核申请。';
		}
		if ( self::pendingFieldExists( 'lr_student_id', $studentId ) || self::studentIdExists( $studentId ) ) {
			$errors[] = '该学号已存在。';
		}
		if ( self::pendingFieldExists( 'lr_email', $email ) || self::emailExists( $email ) ) {
			$errors[] = '该邮箱已存在。';
		}

		return $errors;
	}

	public static function createSignupRequest( array $data ): int {
		$dbw = self::getDbw();
		$dbw->newInsertQueryBuilder()
			->insertInto( 'labauth_registration_requests' )
			->row( [
				'lr_username' => trim( (string)$data['username'] ),
				'lr_real_name' => trim( (string)$data['real_name'] ),
				'lr_student_id' => trim( (string)$data['student_id'] ),
				'lr_email' => trim( (string)$data['email'] ),
				'lr_password_hash' => self::encryptPendingPassword( (string)$data['password'] ),
				'lr_status' => self::STATUS_PENDING,
				'lr_submitted_at' => $dbw->timestamp()
			] )
			->caller( __METHOD__ )
			->execute();

		return (int)$dbw->insertId();
	}

	public static function getSignupRequestStatus( int $requestId ): ?array {
		$row = self::getDbr()->newSelectQueryBuilder()
			->select( [
				'lr_id',
				'lr_username',
				'lr_status',
				'lr_review_note',
				'lr_submitted_at',
				'lr_reviewed_at'
			] )
			->from( 'labauth_registration_requests' )
			->where( [ 'lr_id' => $requestId ] )
			->caller( __METHOD__ )
			->fetchRow();

		return $row ? self::formatRequestRow( $row ) : null;
	}

	public static function getPendingRequests(): array {
		$res = self::getDbr()->newSelectQueryBuilder()
			->select( '*' )
			->from( 'labauth_registration_requests' )
			->where( [ 'lr_status' => self::STATUS_PENDING ] )
			->orderBy( 'lr_submitted_at', SelectQueryBuilder::SORT_DESC )
			->caller( __METHOD__ )
			->fetchResultSet();

		$items = [];
		foreach ( $res as $row ) {
			$items[] = self::formatRequestRow( $row );
		}
		return $items;
	}

	public static function getReviewedRequests( int $limit = 20 ): array {
		$res = self::getDbr()->newSelectQueryBuilder()
			->select( '*' )
			->from( 'labauth_registration_requests' )
			->where( self::getDbr()->expr( 'lr_status', '!=', self::STATUS_PENDING ) )
			->orderBy( 'lr_reviewed_at', SelectQueryBuilder::SORT_DESC )
			->limit( $limit )
			->caller( __METHOD__ )
			->fetchResultSet();

		$items = [];
		foreach ( $res as $row ) {
			$items[] = self::formatRequestRow( $row );
		}

		return $items;
	}

	public static function getAdminEvents( int $limit = 50 ): array {
		$res = self::getDbr()->newSelectQueryBuilder()
			->select( '*' )
			->from( 'labauth_admin_events' )
			->orderBy( 'lae_created_at', SelectQueryBuilder::SORT_DESC )
			->limit( $limit )
			->caller( __METHOD__ )
			->fetchResultSet();

		$items = [];
		foreach ( $res as $row ) {
			$items[] = self::formatAdminEventRow( $row );
		}

		return $items;
	}

	public static function getManagedUsers(): array {
		$res = self::getDbr()->newSelectQueryBuilder()
			->select( [
				'user_id',
				'user_name',
				'user_real_name',
				'user_email',
				'student_id' => 'lup.lup_student_id',
				'account_status' => 'lup.lup_account_status',
				'approved_at' => 'lup.lup_approved_at'
			] )
			->from( 'user' )
			->join( 'labauth_user_profiles', 'lup', 'lup.lup_user = user_id' )
			->orderBy( 'user_id', SelectQueryBuilder::SORT_DESC )
			->caller( __METHOD__ )
			->fetchResultSet();

		$items = [];
		foreach ( $res as $row ) {
			$items[] = [
				'user_id' => (int)$row->user_id,
				'username' => (string)$row->user_name,
				'real_name' => (string)$row->user_real_name,
				'email' => (string)$row->user_email,
				'student_id' => (string)$row->student_id,
				'account_status' => (string)$row->account_status,
				'approved_at' => (string)$row->approved_at,
			];
		}

		return $items;
	}

	public static function approveSignupRequest( int $requestId, User $reviewer, string $reviewNote = '' ): array {
		$dbw = self::getDbw();
		$row = $dbw->newSelectQueryBuilder()
			->select( '*' )
			->from( 'labauth_registration_requests' )
			->where( [
				'lr_id' => $requestId,
				'lr_status' => self::STATUS_PENDING
			] )
			->caller( __METHOD__ )
			->fetchRow();

		if ( !$row ) {
			throw new \RuntimeException( '待审核申请不存在。' );
		}

		$username = (string)$row->lr_username;
		if ( self::userExists( $username ) ) {
			throw new \RuntimeException( '该用户名已被占用。' );
		}
		if ( self::emailExists( (string)$row->lr_email ) ) {
			throw new \RuntimeException( '该邮箱已被占用。' );
		}
		if ( self::studentIdExists( (string)$row->lr_student_id ) ) {
			throw new \RuntimeException( '该学号已被占用。' );
		}
		$password = self::decryptPendingPassword( (string)$row->lr_password_hash );

		$authManager = MediaWikiServices::getInstance()->getAuthManager();
		$authRequests = $authManager->getAuthenticationRequests( AuthManager::ACTION_CREATE, $reviewer );
		$authRequests = AuthenticationRequest::loadRequestsFromSubmission(
			$authRequests,
			[
				'username' => $username,
				'password' => $password,
				'retype' => $password,
				'email' => (string)$row->lr_email,
				'realname' => (string)$row->lr_real_name,
			]
		);
		$response = $authManager->beginAccountCreation(
			RequestContext::getMain()->getAuthority(),
			$authRequests,
			SpecialPage::getTitleFor( 'LabAccountAdmin' )->getFullURL()
		);
		if ( $response->status !== AuthenticationResponse::PASS ) {
			$message = $response->message ? $response->message->text() : '创建 MediaWiki 账号失败。';
			throw new \RuntimeException( $message );
		}

		$user = User::newFromName( $username, 'usable' );
		if ( !$user || !$user->isRegistered() ) {
			throw new \RuntimeException( '创建 MediaWiki 账号失败。' );
		}

		MediaWikiServices::getInstance()->getUserGroupManager()
			->addUserToGroup( $user, 'student' );

		$dbw->newReplaceQueryBuilder()
			->replaceInto( 'labauth_user_profiles' )
			->uniqueIndexFields( [ 'lup_user' ] )
			->row( [
				'lup_user' => $user->getId(),
				'lup_student_id' => (string)$row->lr_student_id,
				'lup_account_status' => self::ACCOUNT_ACTIVE,
				'lup_approved_at' => $dbw->timestamp(),
				'lup_approved_by' => $reviewer->getId()
			] )
			->caller( __METHOD__ )
			->execute();

		$dbw->newUpdateQueryBuilder()
			->update( 'labauth_registration_requests' )
			->set( [
				'lr_status' => self::STATUS_APPROVED,
				'lr_review_note' => $reviewNote,
				'lr_reviewed_at' => $dbw->timestamp(),
				'lr_reviewed_by' => $reviewer->getId()
			] )
			->where( [ 'lr_id' => $requestId ] )
			->caller( __METHOD__ )
			->execute();

		self::recordAdminEvent(
			'request_approved',
			$reviewer,
			[
				'target_user' => (int)$user->getId(),
				'target_username' => $user->getName(),
				'request_id' => $requestId,
				'summary' => '审批通过：' . $user->getName(),
				'details_text' => '申请人：' . (string)$row->lr_real_name .
					'；学号：' . (string)$row->lr_student_id
			]
		);

		return [
			'request_id' => $requestId,
			'user_id' => (int)$user->getId(),
			'username' => $username,
			'status' => self::STATUS_APPROVED
		];
	}

	public static function rejectSignupRequest( int $requestId, User $reviewer, string $reviewNote = '' ): void {
		$dbw = self::getDbw();
		$row = $dbw->newSelectQueryBuilder()
			->select( '*' )
			->from( 'labauth_registration_requests' )
			->where( [
				'lr_id' => $requestId,
				'lr_status' => self::STATUS_PENDING
			] )
			->caller( __METHOD__ )
			->fetchRow();

		if ( !$row ) {
			throw new \RuntimeException( '待审核申请不存在。' );
		}

		$affected = $dbw->newUpdateQueryBuilder()
			->update( 'labauth_registration_requests' )
			->set( [
				'lr_status' => self::STATUS_REJECTED,
				'lr_review_note' => $reviewNote,
				'lr_reviewed_at' => $dbw->timestamp(),
				'lr_reviewed_by' => $reviewer->getId()
			] )
			->where( [
				'lr_id' => $requestId,
				'lr_status' => self::STATUS_PENDING
			] )
			->caller( __METHOD__ );
		$affected->execute();

		if ( !$dbw->affectedRows() ) {
			throw new \RuntimeException( '待审核申请不存在。' );
		}

		self::recordAdminEvent(
			'request_rejected',
			$reviewer,
			[
				'target_user' => 0,
				'target_username' => (string)$row->lr_username,
				'request_id' => $requestId,
				'summary' => '驳回申请：' . (string)$row->lr_username,
				'details_text' => $reviewNote !== '' ? $reviewNote : '未填写驳回原因'
			]
		);
	}

	public static function setAccountStatus( int $userId, string $status, User $actor ): void {
		$dbw = self::getDbw();
		$user = User::newFromId( $userId );
		if ( !$user || !$user->isRegistered() ) {
			throw new \RuntimeException( '目标账户不存在。' );
		}
		$query = $dbw->newUpdateQueryBuilder()
			->update( 'labauth_user_profiles' )
			->set( [ 'lup_account_status' => $status ] )
			->where( [ 'lup_user' => $userId ] )
			->caller( __METHOD__ );
		$query->execute();

		if ( !$dbw->affectedRows() ) {
			throw new \RuntimeException( '账户资料不存在。' );
		}

		self::recordAdminEvent(
			$status === self::ACCOUNT_DISABLED ? 'account_disabled' : 'account_enabled',
			$actor,
			[
				'target_user' => $userId,
				'target_username' => $user->getName(),
				'summary' => ( $status === self::ACCOUNT_DISABLED ? '停用账户：' : '恢复账户：' ) . $user->getName(),
				'details_text' => ''
			]
		);
	}

	public static function resetPassword( int $userId, string $newPassword, User $actor ): void {
		$user = User::newFromId( $userId );
		if ( !$user || !$user->isRegistered() ) {
			throw new \RuntimeException( '目标账户不存在。' );
		}

		$status = $user->checkPasswordValidity( $newPassword );
		if ( !$status->isGood() ) {
			throw new \RuntimeException( $status->getMessage()->text() );
		}

		$changeStatus = $user->changeAuthenticationData( [
			'username' => $user->getName(),
			'password' => $newPassword
		] );
		if ( !$changeStatus->isGood() ) {
			throw new \RuntimeException( $changeStatus->getMessage()->text() );
		}

		self::recordAdminEvent(
			'password_reset',
			$actor,
			[
				'target_user' => $userId,
				'target_username' => $user->getName(),
				'summary' => '重置密码：' . $user->getName(),
				'details_text' => '密码已由管理员重置'
			]
		);
	}

	public static function isUserDisabled( User $user ): bool {
		if ( !$user->isRegistered() ) {
			return false;
		}

		$status = self::getDbr()->newSelectQueryBuilder()
			->select( 'lup_account_status' )
			->from( 'labauth_user_profiles' )
			->where( [ 'lup_user' => $user->getId() ] )
			->caller( __METHOD__ )
			->fetchField();

		return $status === self::ACCOUNT_DISABLED;
	}

	private static function userExists( string $username ): bool {
		return (bool)self::getDbr()->newSelectQueryBuilder()
			->select( 'user_id' )
			->from( 'user' )
			->where( [ 'user_name' => $username ] )
			->caller( __METHOD__ )
			->fetchField();
	}

	private static function emailExists( string $email ): bool {
		return (bool)self::getDbr()->newSelectQueryBuilder()
			->select( 'user_id' )
			->from( 'user' )
			->where( [ 'user_email' => $email ] )
			->caller( __METHOD__ )
			->fetchField();
	}

	private static function studentIdExists( string $studentId ): bool {
		return (bool)self::getDbr()->newSelectQueryBuilder()
			->select( 'lup_user' )
			->from( 'labauth_user_profiles' )
			->where( [ 'lup_student_id' => $studentId ] )
			->caller( __METHOD__ )
			->fetchField();
	}

	private static function pendingFieldExists( string $field, string $value ): bool {
		return (bool)self::getDbr()->newSelectQueryBuilder()
			->select( 'lr_id' )
			->from( 'labauth_registration_requests' )
			->where( [
				$field => $value,
				'lr_status' => self::STATUS_PENDING
			] )
			->caller( __METHOD__ )
			->fetchField();
	}

	private static function encryptPendingPassword( string $password ): string {
		$key = hash( 'sha256', (string)( $GLOBALS['wgSecretKey'] ?? 'labwiki-labauth' ), true );
		$iv = random_bytes( 16 );
		$ciphertext = openssl_encrypt(
			$password,
			'aes-256-cbc',
			$key,
			OPENSSL_RAW_DATA,
			$iv
		);
		if ( $ciphertext === false ) {
			throw new \RuntimeException( '注册密码加密失败。' );
		}

		return 'enc:v1:' . base64_encode( $iv . $ciphertext );
	}

	private static function decryptPendingPassword( string $encoded ): string {
		if ( !str_starts_with( $encoded, 'enc:v1:' ) ) {
			throw new \RuntimeException( '该申请使用旧版密码存储方式，请让申请人重新提交注册。' );
		}

		$raw = base64_decode( substr( $encoded, 7 ), true );
		if ( $raw === false || strlen( $raw ) <= 16 ) {
			throw new \RuntimeException( '注册密码解密失败。' );
		}

		$key = hash( 'sha256', (string)( $GLOBALS['wgSecretKey'] ?? 'labwiki-labauth' ), true );
		$iv = substr( $raw, 0, 16 );
		$ciphertext = substr( $raw, 16 );
		$password = openssl_decrypt(
			$ciphertext,
			'aes-256-cbc',
			$key,
			OPENSSL_RAW_DATA,
			$iv
		);
		if ( !is_string( $password ) || $password === '' ) {
			throw new \RuntimeException( '注册密码解密失败。' );
		}

		return $password;
	}

	private static function formatRequestRow( object $row ): array {
		$reviewedBy = isset( $row->lr_reviewed_by ) ? (int)$row->lr_reviewed_by : 0;
		return [
			'request_id' => (int)$row->lr_id,
			'username' => (string)$row->lr_username,
			'real_name' => (string)$row->lr_real_name,
			'student_id' => (string)$row->lr_student_id,
			'email' => (string)$row->lr_email,
			'status' => (string)$row->lr_status,
			'review_note' => isset( $row->lr_review_note ) ? (string)$row->lr_review_note : '',
			'submitted_at' => (string)$row->lr_submitted_at,
			'reviewed_at' => isset( $row->lr_reviewed_at ) ? (string)$row->lr_reviewed_at : '',
			'reviewed_by' => $reviewedBy,
			'reviewed_by_name' => self::getReviewerDisplayName( $reviewedBy ),
		];
	}

	private static function formatAdminEventRow( object $row ): array {
		return [
			'event_id' => (int)$row->lae_id,
			'event_type' => (string)$row->lae_event_type,
			'actor_user' => isset( $row->lae_actor_user ) ? (int)$row->lae_actor_user : 0,
			'actor_name' => (string)$row->lae_actor_name,
			'target_user' => isset( $row->lae_target_user ) ? (int)$row->lae_target_user : 0,
			'target_username' => isset( $row->lae_target_username ) ? (string)$row->lae_target_username : '',
			'request_id' => isset( $row->lae_request_id ) ? (int)$row->lae_request_id : 0,
			'summary' => (string)$row->lae_summary,
			'details_text' => isset( $row->lae_details_text ) ? (string)$row->lae_details_text : '',
			'created_at' => (string)$row->lae_created_at,
		];
	}

	private static function recordAdminEvent( string $eventType, User $actor, array $payload ): void {
		$dbw = self::getDbw();
		$actorName = trim( (string)$actor->getRealName() );
		if ( $actorName === '' ) {
			$actorName = $actor->getName();
		}

		$dbw->newInsertQueryBuilder()
			->insertInto( 'labauth_admin_events' )
			->row( [
				'lae_event_type' => $eventType,
				'lae_actor_user' => $actor->isRegistered() ? $actor->getId() : null,
				'lae_actor_name' => $actorName,
				'lae_target_user' => !empty( $payload['target_user'] ) ? (int)$payload['target_user'] : null,
				'lae_target_username' => isset( $payload['target_username'] ) ? (string)$payload['target_username'] : null,
				'lae_request_id' => !empty( $payload['request_id'] ) ? (int)$payload['request_id'] : null,
				'lae_summary' => (string)( $payload['summary'] ?? $eventType ),
				'lae_details_text' => isset( $payload['details_text'] ) ? (string)$payload['details_text'] : null,
				'lae_created_at' => $dbw->timestamp()
			] )
			->caller( __METHOD__ )
			->execute();
	}

	private static function getReviewerDisplayName( int $userId ): string {
		if ( $userId <= 0 ) {
			return '';
		}

		$user = User::newFromId( $userId );
		if ( !$user || !$user->isRegistered() ) {
			return '';
		}

		$realName = trim( (string)$user->getRealName() );
		if ( $realName !== '' ) {
			return $realName;
		}

		return $user->getName();
	}
}
