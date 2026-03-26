<?php

namespace MediaWiki\Extension\LabWorkbook;

use CommentStoreComment;
use MediaWiki\Content\TextContent;
use MediaWiki\Content\WikitextContent;
use MediaWiki\MediaWikiServices;
use MediaWiki\Revision\SlotRecord;
use MediaWiki\User\User;
use RuntimeException;
use Wikimedia\Rdbms\IDatabase;
use Wikimedia\Rdbms\SelectQueryBuilder;

class WorkbookStore {
	private const FACTS_START = '<!-- LABWORKBOOK_FACTS_START -->';
	private const FACTS_END = '<!-- LABWORKBOOK_FACTS_END -->';

	private static function getDbw(): IDatabase {
		return MediaWikiServices::getInstance()->getConnectionProvider()->getPrimaryDatabase();
	}

	private static function getDbr(): IDatabase {
		return MediaWikiServices::getInstance()->getConnectionProvider()->getReplicaDatabase();
	}

	private static function getSeedDir(): string {
		return '/opt/labwiki/seed/private/workbooks';
	}

	public static function ensureSeedImported(): void {
		$count = (int)self::getDbr()->newSelectQueryBuilder()
			->select( 'COUNT(*)' )
			->from( 'labworkbook_workbooks' )
			->caller( __METHOD__ )
			->fetchField();

		if ( $count > 0 ) {
			return;
		}

		self::importSeedWorkbooks();
	}

	public static function getWorkbookSummaries(): array {
		self::ensureSeedImported();

		$res = self::getDbr()->newSelectQueryBuilder()
			->select( '*' )
			->from( 'labworkbook_workbooks' )
			->orderBy( 'labw_slug', SelectQueryBuilder::SORT_ASC )
			->caller( __METHOD__ )
			->fetchResultSet();

		$items = [];
		foreach ( $res as $row ) {
			$summary = self::formatWorkbookRow( $row );
			$summary['sheet_count'] = self::countSheets( (int)$row->labw_id );
			unset( $summary['metadata'] );
			$items[] = $summary;
		}

		return $items;
	}

	public static function getWorkbookBySlug( string $slug ): ?array {
		self::ensureSeedImported();
		$row = self::findWorkbookRow( $slug, false );
		if ( !$row ) {
			return null;
		}

		return self::hydrateWorkbook( $row );
	}

	public static function saveWorkbookChanges( string $slug, array $changes ): array {
		self::ensureSeedImported();
		$dbw = self::getDbw();
		$row = self::findWorkbookRow( $slug, true );
		if ( !$row ) {
			throw new RuntimeException( '未找到对应的实验工作簿。' );
		}

		$updates = [
			'labw_updated_at' => $dbw->timestamp()
		];
		$hasWorkbookUpdate = false;
		$runLabel = $changes['run_label'];
		if ( $runLabel !== null ) {
			$updates['labw_run_label'] = trim( (string)$runLabel );
			$hasWorkbookUpdate = true;
		}

		if ( $hasWorkbookUpdate ) {
			$dbw->newUpdateQueryBuilder()
				->update( 'labworkbook_workbooks' )
				->set( $updates )
				->where( [ 'labw_id' => (int)$row->labw_id ] )
				->caller( __METHOD__ )
				->execute();
		}

		$sheetKey = trim( (string)( $changes['sheet_key'] ?? '' ) );
		$sheetData = $changes['sheet_data'] ?? null;
		if ( $sheetKey !== '' && $sheetData !== null ) {
			$decoded = json_decode( (string)$sheetData, true );
			if ( !is_array( $decoded ) ) {
				throw new RuntimeException( '工作表数据格式无效。' );
			}

			$dbw->newUpdateQueryBuilder()
				->update( 'labworkbook_sheets' )
				->set( [
					'labws_data' => json_encode( $decoded, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES ),
					'labws_updated_at' => $dbw->timestamp()
				] )
				->where( [
					'labws_workbook_id' => (int)$row->labw_id,
					'labws_sheet_key' => $sheetKey
				] )
				->caller( __METHOD__ )
				->execute();
		}

		$updated = self::getWorkbookBySlug( $slug );
		if ( !$updated ) {
			throw new RuntimeException( '保存后未能重新读取实验工作簿。' );
		}

		return $updated;
	}

	public static function upsertShotPage( string $slug, string $sheetKey, int $rowIndex, User $user ): array {
		$workbook = self::getWorkbookBySlug( $slug );
		if ( !$workbook ) {
			throw new RuntimeException( '未找到对应的实验工作簿。' );
		}
		if ( trim( (string)( $workbook['run_label'] ?? '' ) ) === '' ) {
			throw new RuntimeException( '请先为工作簿填写 Run 标签，再生成 Shot 页面。' );
		}

		$sheet = null;
		foreach ( $workbook['sheets'] as $candidate ) {
			if ( (string)$candidate['sheet_key'] === $sheetKey ) {
				$sheet = $candidate;
				break;
			}
		}
		if ( !$sheet ) {
			throw new RuntimeException( '未找到对应的工作表。' );
		}
		if ( (string)( $sheet['type'] ?? '' ) !== 'main_log' ) {
			throw new RuntimeException( '只有主台账工作表支持生成 Shot 页面。' );
		}
		if ( $rowIndex < 0 || !isset( $sheet['rows'][$rowIndex] ) || !is_array( $sheet['rows'][$rowIndex] ) ) {
			throw new RuntimeException( '未找到对应的主台账行。' );
		}

		$row = $sheet['rows'][$rowIndex];
		$pageTitle = self::buildShotPageTitle( (string)$workbook['run_label'], $row );
		if ( $pageTitle === '' ) {
			throw new RuntimeException( '当前行缺少日期或 No，无法生成 Shot 页面标题。' );
		}

		$title = \Title::newFromText( $pageTitle );
		if ( !$title ) {
			throw new RuntimeException( '生成的 Shot 页面标题无效。' );
		}

		$wikiPage = MediaWikiServices::getInstance()->getWikiPageFactory()->newFromTitle( $title );
		$currentText = self::getPageText( $wikiPage->getContent() );
		$pageText = self::upsertManagedShotFactsBlock(
			$currentText,
			self::buildShotFactsBlock( self::buildShotFactsParameters( $pageTitle, $workbook, $row ) )
		);

		$updater = $wikiPage->newPageUpdater( $user );
		$updater->setContent( SlotRecord::MAIN, new WikitextContent( $pageText ) );
		$updater->saveRevision(
			CommentStoreComment::newUnsavedComment( 'Sync shot facts from LabWorkbook' ),
			0
		);

		return [
			'page_title' => $pageTitle,
			'page_url' => $title->getFullURL()
		];
	}

	private static function importSeedWorkbooks(): void {
		$seedDir = self::getSeedDir();
		if ( !is_dir( $seedDir ) ) {
			return;
		}

		$files = glob( $seedDir . '/*.json' ) ?: [];
		sort( $files, SORT_NATURAL );
		foreach ( $files as $file ) {
			$decoded = json_decode( (string)file_get_contents( $file ), true );
			if ( !is_array( $decoded ) || !isset( $decoded['slug'] ) ) {
				continue;
			}
			self::upsertWorkbookPayload( $decoded );
		}
	}

	private static function upsertWorkbookPayload( array $payload ): void {
		$dbw = self::getDbw();
		$slug = trim( (string)( $payload['slug'] ?? '' ) );
		if ( $slug === '' ) {
			return;
		}

		$row = self::findWorkbookRow( $slug, true );
		$timestamp = $dbw->timestamp();
		if ( !$row ) {
			$dbw->newInsertQueryBuilder()
				->insertInto( 'labworkbook_workbooks' )
				->row( [
					'labw_slug' => $slug,
					'labw_title' => (string)( $payload['title'] ?? $slug ),
					'labw_source_filename' => (string)( $payload['source_filename'] ?? '' ),
					'labw_run_label' => trim( (string)( $payload['run_label'] ?? '' ) ),
					'labw_metadata' => json_encode( [
						'imported_from_seed' => true
					], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES ),
					'labw_created_at' => $timestamp,
					'labw_updated_at' => $timestamp
				] )
				->caller( __METHOD__ )
				->execute();
			$workbookId = (int)$dbw->insertId();
		} else {
			$workbookId = (int)$row->labw_id;
			$dbw->newUpdateQueryBuilder()
				->update( 'labworkbook_workbooks' )
				->set( [
					'labw_title' => (string)( $payload['title'] ?? $slug ),
					'labw_source_filename' => (string)( $payload['source_filename'] ?? '' ),
					'labw_run_label' => trim( (string)( $payload['run_label'] ?? '' ) ),
					'labw_updated_at' => $timestamp
				] )
				->where( [ 'labw_id' => $workbookId ] )
				->caller( __METHOD__ )
				->execute();
		}

		foreach ( (array)( $payload['sheets'] ?? [] ) as $sheet ) {
			$sheetKey = trim( (string)( $sheet['sheet_key'] ?? '' ) );
			if ( $sheetKey === '' ) {
				continue;
			}

			$existingSheet = $dbw->newSelectQueryBuilder()
				->select( [ 'labws_id' ] )
				->from( 'labworkbook_sheets' )
				->where( [
					'labws_workbook_id' => $workbookId,
					'labws_sheet_key' => $sheetKey
				] )
				->caller( __METHOD__ )
				->fetchRow();

			$rowData = [
				'labws_workbook_id' => $workbookId,
				'labws_sheet_key' => $sheetKey,
				'labws_sheet_name' => (string)( $sheet['sheet_name'] ?? $sheetKey ),
				'labws_sheet_type' => (string)( $sheet['type'] ?? 'matrix' ),
				'labws_position' => (int)( $sheet['position'] ?? 0 ),
				'labws_data' => json_encode( $sheet, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES ),
				'labws_updated_at' => $timestamp
			];

			if ( $existingSheet ) {
				$dbw->newUpdateQueryBuilder()
					->update( 'labworkbook_sheets' )
					->set( $rowData )
					->where( [ 'labws_id' => (int)$existingSheet->labws_id ] )
					->caller( __METHOD__ )
					->execute();
			} else {
				$dbw->newInsertQueryBuilder()
					->insertInto( 'labworkbook_sheets' )
					->row( $rowData )
					->caller( __METHOD__ )
					->execute();
			}
		}
	}

	private static function findWorkbookRow( string $slug, bool $primary ) {
		$db = $primary ? self::getDbw() : self::getDbr();
		return $db->newSelectQueryBuilder()
			->select( '*' )
			->from( 'labworkbook_workbooks' )
			->where( [ 'labw_slug' => $slug ] )
			->caller( __METHOD__ )
			->fetchRow();
	}

	private static function countSheets( int $workbookId ): int {
		return (int)self::getDbr()->newSelectQueryBuilder()
			->select( 'COUNT(*)' )
			->from( 'labworkbook_sheets' )
			->where( [ 'labws_workbook_id' => $workbookId ] )
			->caller( __METHOD__ )
			->fetchField();
	}

	private static function hydrateWorkbook( $row ): array {
		$item = self::formatWorkbookRow( $row );
		$res = self::getDbr()->newSelectQueryBuilder()
			->select( '*' )
			->from( 'labworkbook_sheets' )
			->where( [ 'labws_workbook_id' => (int)$row->labw_id ] )
			->orderBy( 'labws_position', SelectQueryBuilder::SORT_ASC )
			->caller( __METHOD__ )
			->fetchResultSet();

		$item['sheets'] = [];
		foreach ( $res as $sheetRow ) {
			$item['sheets'][] = self::formatSheetRow( $sheetRow );
		}
		return $item;
	}

	private static function formatWorkbookRow( $row ): array {
		$metadata = json_decode( (string)( $row->labw_metadata ?? '' ), true );
		return [
			'id' => (int)$row->labw_id,
			'slug' => (string)$row->labw_slug,
			'title' => (string)$row->labw_title,
			'source_filename' => (string)$row->labw_source_filename,
			'run_label' => (string)$row->labw_run_label,
			'created_at' => (string)$row->labw_created_at,
			'updated_at' => (string)$row->labw_updated_at,
			'metadata' => is_array( $metadata ) ? $metadata : []
		];
	}

	private static function formatSheetRow( $row ): array {
		$data = json_decode( (string)$row->labws_data, true );
		if ( !is_array( $data ) ) {
			$data = [];
		}
		$data['sheet_key'] = (string)$row->labws_sheet_key;
		$data['sheet_name'] = (string)$row->labws_sheet_name;
		$data['type'] = (string)$row->labws_sheet_type;
		$data['position'] = (int)$row->labws_position;
		return $data;
	}

	private static function normalizeDatePart( string $rawValue ): string {
		if ( !preg_match( '/^(\\d{4})[-\\/](\\d{1,2})[-\\/](\\d{1,2})/', trim( $rawValue ), $matched ) ) {
			return '';
		}

		return sprintf(
			'%s-%02d-%02d',
			$matched[1],
			(int)$matched[2],
			(int)$matched[3]
		);
	}

	private static function buildShotPageTitle( string $runLabel, array $row ): string {
		$datePart = self::normalizeDatePart( (string)( $row['时间'] ?? $row['日期'] ?? '' ) );
		$shotNo = trim( (string)( $row['No'] ?? '' ) );
		if ( $datePart === '' || trim( $runLabel ) === '' || !preg_match( '/^\\d+$/', $shotNo ) ) {
			return '';
		}

		return sprintf( 'Shot:%s-%s-Shot%03d', $datePart, trim( $runLabel ), (int)$shotNo );
	}

	private static function getPageText( $content ): string {
		if ( $content instanceof TextContent ) {
			return $content->getText();
		}
		return '';
	}

	private static function buildShotFactsParameters( string $pageTitle, array $workbook, array $row ): array {
		return [
			'Shot编号' => $pageTitle,
			'日期' => self::normalizeDatePart( (string)( $row['时间'] ?? $row['日期'] ?? '' ) ),
			'Run' => (string)$workbook['run_label'],
			'时间' => (string)( $row['时间'] ?? '' ),
			'主台账No' => (string)( $row['No'] ?? '' ),
			'页面状态' => '草稿',
			'压缩后' => (string)( $row['压缩后'] ?? '' ),
			'脉宽' => (string)( $row['压缩后'] ?? '' ),
			'反射率' => (string)( $row['反射率'] ?? '' ),
			'小靶偏振片角度' => (string)( $row['小靶偏振片角度'] ?? '' ),
			'靶类型' => (string)( $row['靶类型'] ?? '' ),
			'靶位' => (string)( $row['靶位'] ?? '' ),
			'靶离焦' => (string)( $row['靶离焦'] ?? '' ),
			'光栅' => (string)( $row['光栅'] ?? '' ),
			'PM' => (string)( $row['PM'] ?? '' ),
			'PM离焦' => (string)( $row['PM离焦'] ?? '' ),
			'闪烁光纤质子能量' => (string)( $row['闪烁光纤质子能量'] ?? '' ),
			'TPS_H能量' => (string)( $row['TPS: H+能量'] ?? '' ),
			'TPS_C6能量' => (string)( $row['TPS: C6能量'] ?? '' ),
			'备注' => (string)( $row['备注'] ?? '' ),
			'315漏光' => (string)( $row['315漏光'] ?? '' ),
			'靶前监测' => (string)( $row['靶前监测'] ?? '' ),
			'有没有膜' => (string)( $row['有没有膜'] ?? '' ),
			'EMP振幅' => (string)( $row['EMP振幅'] ?? '' ),
			'列21' => (string)( $row['列21'] ?? '' ),
			'列22' => (string)( $row['列22'] ?? '' ),
			'列23' => (string)( $row['列23'] ?? '' ),
			'列24' => (string)( $row['列24'] ?? '' ),
			'W1_mJ' => (string)( $row['W1 [mJ]'] ?? '' ),
			'透射率' => (string)( $row['透射率'] ?? '' ),
			'原始数据主目录' => sprintf(
				'%s/%s/Shot%03d/',
				str_replace( '-', '', self::normalizeDatePart( (string)( $row['时间'] ?? $row['日期'] ?? '' ) ) ),
				(string)$workbook['run_label'],
				(int)( $row['No'] ?? 0 )
			)
		];
	}

	private static function buildShotFactsBlock( array $params ): string {
		$lines = [ self::FACTS_START, '{{Shot记录' ];
		foreach ( $params as $key => $value ) {
			if ( $value === '' || $value === null ) {
				continue;
			}
			$normalized = str_replace(
				[ "\r\n", "\r", "\n", '|' ],
				[ ' ', ' ', ' ', '&#124;' ],
				trim( (string)$value )
			);
			$lines[] = sprintf( '|%s=%s', $key, $normalized );
		}
		$lines[] = '}}';
		$lines[] = self::FACTS_END;
		return implode( "\n", $lines );
	}

	private static function upsertManagedShotFactsBlock( string $currentText, string $factsBlock ): string {
		$trimmed = trim( $currentText );
		$pattern = '/' . preg_quote( self::FACTS_START, '/' ) . '.*?' . preg_quote( self::FACTS_END, '/' ) . '\\s*/s';

		if ( preg_match( $pattern, $trimmed ) ) {
			$updated = preg_replace( $pattern, $factsBlock . "\n\n", $trimmed, 1 );
			return is_string( $updated ) ? trim( $updated ) . "\n" : $factsBlock . "\n";
		}

		if ( $trimmed === '' ) {
			return $factsBlock . "\n";
		}

		return $factsBlock . "\n\n" . $trimmed . "\n";
	}
}
