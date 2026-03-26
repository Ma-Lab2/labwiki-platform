CREATE TABLE /*_*/labauth_registration_requests (
  lr_id int unsigned NOT NULL AUTO_INCREMENT,
  lr_username varbinary(255) NOT NULL,
  lr_real_name varbinary(255) NOT NULL,
  lr_student_id varbinary(64) NOT NULL,
  lr_email varbinary(255) NOT NULL,
  lr_password_hash blob NOT NULL,
  lr_status varbinary(32) NOT NULL,
  lr_review_note blob DEFAULT NULL,
  lr_submitted_at binary(14) NOT NULL,
  lr_reviewed_at binary(14) DEFAULT NULL,
  lr_reviewed_by int unsigned DEFAULT NULL,
  PRIMARY KEY (lr_id),
  UNIQUE KEY lr_username_status (lr_username, lr_status),
  KEY lr_status_submitted (lr_status, lr_submitted_at),
  KEY lr_student_id (lr_student_id),
  KEY lr_email (lr_email)
) /*$wgDBTableOptions*/;
