BEGIN TRANSACTION;
CREATE TABLE admin (
	id INTEGER NOT NULL, 
	password_hash VARCHAR NOT NULL, 
	totp_secret VARCHAR NOT NULL, 
	last_totp_step INTEGER NOT NULL, 
	CONSTRAINT pk_admin PRIMARY KEY (id)
);
INSERT INTO "admin" VALUES(1,'$argon2id$v=19$m=19456,t=2,p=1$8dQB7LM1QbRQNuUgMj6XnA$gsjUz1pd4i5p5WdYtxrzDCCtBRbUWgV2AJgHfUASh1M','JBSWY3DPEHPK3PXP',59000000);
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO "alembic_version" VALUES('0001');
CREATE TABLE container (
	id INTEGER NOT NULL, 
	host_id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	docker_id VARCHAR, 
	compose_project VARCHAR, 
	image VARCHAR, 
	tag VARCHAR, 
	enabled BOOLEAN NOT NULL, 
	release_source VARCHAR, 
	source_confirmed BOOLEAN NOT NULL, 
	CONSTRAINT pk_container PRIMARY KEY (id), 
	CONSTRAINT fk_container_host_id_host FOREIGN KEY(host_id) REFERENCES host (id) ON DELETE CASCADE, 
	CONSTRAINT uq_container_host_id_name UNIQUE (host_id, name)
);
INSERT INTO "container" VALUES(1,1,'app','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','demo','example/app','1.0.0',1,'example/app',1);
INSERT INTO "container" VALUES(2,1,'db','bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','demo','example/db','latest',1,NULL,0);
INSERT INTO "container" VALUES(3,1,'excluded',NULL,NULL,'example/off','2',0,NULL,0);
CREATE TABLE event (
	id INTEGER NOT NULL, 
	container_id INTEGER NOT NULL, 
	kind VARCHAR(16) NOT NULL, 
	time DATETIME NOT NULL, 
	CONSTRAINT pk_event PRIMARY KEY (id), 
	CONSTRAINT fk_event_container_id_container FOREIGN KEY(container_id) REFERENCES container (id) ON DELETE CASCADE
);
INSERT INTO "event" VALUES(1,1,'became_unhealthy','2026-01-01 12:00:00.000000');
INSERT INTO "event" VALUES(2,1,'recovered_health','2026-01-01 12:05:00.000000');
CREATE TABLE host (
	id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	CONSTRAINT pk_host PRIMARY KEY (id)
);
INSERT INTO "host" VALUES(1,'local');
CREATE TABLE repo_cache (
	repo VARCHAR NOT NULL, 
	etag VARCHAR, 
	latest_tag VARCHAR, 
	releases JSON NOT NULL, 
	fetched_at DATETIME, 
	error VARCHAR, 
	CONSTRAINT pk_repo_cache PRIMARY KEY (repo)
);
INSERT INTO "repo_cache" VALUES('example/app','W/"fake-etag"','v1.1.0','[{"tag": "v1.1.0", "notes": "Fix CVE-2026-0001.", "draft": false, "prerelease": false}, {"tag": "v1.0.1", "notes": "Small fixes.", "draft": false, "prerelease": false}]','2026-01-01 12:00:00.000000',NULL);
INSERT INTO "repo_cache" VALUES('example/broken',NULL,NULL,'[]','2026-01-01 12:00:00.000000','HTTP 404');
CREATE TABLE session (
	token_hash VARCHAR NOT NULL, 
	created DATETIME NOT NULL, 
	expires DATETIME NOT NULL, 
	last_seen DATETIME NOT NULL, 
	CONSTRAINT pk_session PRIMARY KEY (token_hash)
);
INSERT INTO "session" VALUES('1f6c5885dd7c9cc60b10d325f516118329bb9bef047515ddf049302c47f2b13e','2026-01-01 12:00:00.000000','2026-01-31 12:00:00.000000','2026-01-01 12:00:00.000000');
CREATE TABLE setting (
	"key" VARCHAR NOT NULL, 
	value JSON NOT NULL, 
	CONSTRAINT pk_setting PRIMARY KEY ("key")
);
INSERT INTO "setting" VALUES('check_interval_hours',12);
INSERT INTO "setting" VALUES('restart_count',4);
INSERT INTO "setting" VALUES('restart_window_minutes',15);
INSERT INTO "setting" VALUES('ntfy_url','"https://ntfy.example.test"');
INSERT INTO "setting" VALUES('ntfy_topic','"wt-test"');
INSERT INTO "setting" VALUES('llm_url','"http://llm.example.test:11434"');
INSERT INTO "setting" VALUES('llm_model','"fake-model"');
INSERT INTO "setting" VALUES('public_url','"https://wt.example.test"');
CREATE TABLE "update" (
	id INTEGER NOT NULL, 
	container_id INTEGER NOT NULL, 
	from_version VARCHAR NOT NULL, 
	to_version VARCHAR NOT NULL, 
	severity VARCHAR(8) NOT NULL, 
	summary VARCHAR NOT NULL, 
	release_notes VARCHAR NOT NULL, 
	notified_at DATETIME, 
	CONSTRAINT pk_update PRIMARY KEY (id), 
	CONSTRAINT fk_update_container_id_container FOREIGN KEY(container_id) REFERENCES container (id) ON DELETE CASCADE, 
	CONSTRAINT uq_update_container_id_to_version UNIQUE (container_id, to_version)
);
INSERT INTO "update" VALUES(1,1,'1.0.0','1.1.0','critical','This update fixes a security problem.','Fix CVE-2026-0001.

Small fixes.','2026-01-01 12:00:00.000000');
CREATE INDEX ix_event_container_id ON event (container_id);
CREATE INDEX ix_update_container_id ON "update" (container_id);
COMMIT;
