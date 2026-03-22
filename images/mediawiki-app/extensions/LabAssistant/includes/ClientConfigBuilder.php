<?php

namespace MediaWiki\Extension\LabAssistant;

class ClientConfigBuilder {
	/** @var string[] */
	private const PAGE_FORMS_SPECIAL_PAGE_ALIASES = [ 'FormEdit', '编辑表格' ];

	/**
	 * @param mixed $title
	 * @return array<string,mixed>|null
	 */
	private static function buildFormContext( $title ): ?array {
		if ( !$title || !$title->inNamespace( NS_SPECIAL ) ) {
			return null;
		}

		$text = $title->getText();
		$parts = explode( '/', $text );
		if ( !$parts || !in_array( $parts[0], self::PAGE_FORMS_SPECIAL_PAGE_ALIASES, true ) || count( $parts ) < 2 ) {
			return null;
		}

		$formName = trim( (string)( $parts[1] ?? '' ) );
		$targetTitle = trim( implode( '/', array_slice( $parts, 2 ) ) );

		return [
			'formName' => $formName,
			'targetTitle' => $targetTitle,
		];
	}

	/**
	 * @param string $currentAction
	 * @param string $currentVeAction
	 * @param string $specialPageName
	 * @return string
	 */
	private static function detectEditorMode(
		string $currentAction,
		string $currentVeAction,
		string $specialPageName
	): string {
		if ( $currentVeAction !== '' ) {
			return 'visual_editor';
		}
		if ( $currentAction === 'formedit' || in_array( $specialPageName, self::PAGE_FORMS_SPECIAL_PAGE_ALIASES, true ) ) {
			return 'pageforms_edit';
		}
		if ( $currentAction === 'edit' ) {
			return 'source_edit';
		}
		return 'default';
	}

	/**
	 * @param mixed $user
	 * @param mixed $title
	 * @param mixed $request
	 * @param string $mountMode
	 * @return array<string,mixed>
	 */
	public static function build( $user, $title, $request, string $mountMode ): array {
		$currentTitle = $title ? $title->getPrefixedText() : '';
		$currentAction = $request ? trim( (string)$request->getVal( 'action', 'view' ) ) : 'view';
		$currentVeAction = $request ? trim( (string)$request->getVal( 'veaction', '' ) ) : '';
		$specialPageName = '';
		$formContext = self::buildFormContext( $title );
		if ( $title && $title->inNamespace( NS_SPECIAL ) ) {
			$specialPageName = preg_replace( '/\/.*/', '', $title->getText() );
		}
		$editorMode = self::detectEditorMode( $currentAction, $currentVeAction, $specialPageName );
		$defaultContextTitle = '';
		if ( $title && !$title->inNamespace( NS_SPECIAL ) ) {
			$defaultContextTitle = $currentTitle;
		} elseif ( $formContext && $formContext['targetTitle'] !== '' ) {
			$defaultContextTitle = $formContext['targetTitle'];
		}

		return [
			'apiBase' => $GLOBALS['wgLabAssistantApiBase'] ?? '/tools/assistant/api',
			'draftPrefix' => $GLOBALS['wgLabAssistantDraftPrefix'] ?? '知识助手草稿',
			'modes' => $GLOBALS['wgLabAssistantModes'] ?? [ 'qa', 'compare', 'draft' ],
			'detailLevels' => $GLOBALS['wgLabAssistantDetailLevels'] ?? [ 'intro', 'intermediate', 'research' ],
			'userName' => $user && $user->isRegistered() ? $user->getName() : null,
			'currentTitle' => $currentTitle,
			'defaultContextTitle' => $defaultContextTitle,
			'seedQuestion' => $request ? trim( (string)$request->getVal( 'q', '' ) ) : '',
			'currentAction' => $currentAction,
			'currentVeAction' => $currentVeAction,
			'specialPageName' => $specialPageName,
			'editorMode' => $editorMode,
			'formContext' => $formContext,
			'mountMode' => $mountMode,
		];
	}
}
