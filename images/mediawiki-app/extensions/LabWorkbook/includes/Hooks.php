<?php

namespace MediaWiki\Extension\LabWorkbook;

class Hooks {
	public static function onLoadExtensionSchemaUpdates( $updater ) {
		$updater->addExtensionTable(
			'labworkbook_workbooks',
			__DIR__ . '/../sql/labworkbook_workbooks.sql'
		);
		$updater->addExtensionTable(
			'labworkbook_sheets',
			__DIR__ . '/../sql/labworkbook_sheets.sql'
		);
	}
}
