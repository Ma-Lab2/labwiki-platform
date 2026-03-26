CREATE TABLE /*_*/labauth_user_profiles (
  lup_user int unsigned NOT NULL,
  lup_student_id varbinary(64) NOT NULL,
  lup_account_status varbinary(32) NOT NULL,
  lup_approved_at binary(14) NOT NULL,
  lup_approved_by int unsigned DEFAULT NULL,
  PRIMARY KEY (lup_user),
  UNIQUE KEY lup_student_id (lup_student_id),
  KEY lup_account_status (lup_account_status)
) /*$wgDBTableOptions*/;
