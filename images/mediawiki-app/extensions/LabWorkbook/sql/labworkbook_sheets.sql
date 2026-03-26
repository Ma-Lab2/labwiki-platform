CREATE TABLE /*_*/labworkbook_sheets (
  labws_id int unsigned NOT NULL AUTO_INCREMENT,
  labws_workbook_id int unsigned NOT NULL,
  labws_sheet_key varbinary(128) NOT NULL,
  labws_sheet_name varbinary(255) NOT NULL,
  labws_sheet_type varbinary(64) NOT NULL,
  labws_position int unsigned NOT NULL,
  labws_data mediumblob NOT NULL,
  labws_updated_at binary(14) NOT NULL,
  PRIMARY KEY (labws_id),
  UNIQUE KEY labws_workbook_sheet (labws_workbook_id, labws_sheet_key),
  KEY labws_workbook_position (labws_workbook_id, labws_position)
) /*$wgDBTableOptions*/;
