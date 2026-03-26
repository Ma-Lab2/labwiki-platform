CREATE TABLE /*_*/labauth_admin_events (
  lae_id int unsigned NOT NULL AUTO_INCREMENT,
  lae_event_type varbinary(64) NOT NULL,
  lae_actor_user int unsigned DEFAULT NULL,
  lae_actor_name varbinary(255) NOT NULL,
  lae_target_user int unsigned DEFAULT NULL,
  lae_target_username varbinary(255) DEFAULT NULL,
  lae_request_id int unsigned DEFAULT NULL,
  lae_summary blob NOT NULL,
  lae_details_text blob DEFAULT NULL,
  lae_created_at binary(14) NOT NULL,
  PRIMARY KEY (lae_id),
  KEY lae_created_at (lae_created_at),
  KEY lae_event_type_created (lae_event_type, lae_created_at),
  KEY lae_target_user (lae_target_user),
  KEY lae_request_id (lae_request_id)
) /*$wgDBTableOptions*/;
