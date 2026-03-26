CREATE TABLE /*_*/labworkbook_workbooks (
  labw_id int unsigned NOT NULL AUTO_INCREMENT,
  labw_slug varbinary(64) NOT NULL,
  labw_title varbinary(255) NOT NULL,
  labw_source_filename varbinary(255) NOT NULL,
  labw_run_label varbinary(64) NOT NULL,
  labw_metadata blob DEFAULT NULL,
  labw_created_at binary(14) NOT NULL,
  labw_updated_at binary(14) NOT NULL,
  PRIMARY KEY (labw_id),
  UNIQUE KEY labw_slug (labw_slug)
) /*$wgDBTableOptions*/;
