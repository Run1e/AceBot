-- ALTER TYPE mod_event_type RENAME VALUE 'MUTE' TO 'TIMEOUT';
-- ALTER TYPE security_action RENAME VALUE 'MUTE' TO 'TIMEOUT';
-- ALTER TABLE mod_timer ADD COLUMN completed BOOLEAN NOT NULL DEFAULT FALSE;
-- DROP TABLE docs_param;
-- alter table log add column type command_type not null default 'PREFIX';
-- should also alter the above one to not have a default value anymore after rows have been set
-- alter table mod_timer drop constraint mod_timer_guild_id_user_id_event_key;
-- also make sure help_claim has correct owner

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mod_event_type') THEN
		CREATE TYPE mod_event_type AS ENUM ('BAN', 'TIMEOUT');
    END IF;

	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'security_action') THEN
		CREATE TYPE security_action AS ENUM ('TIMEOUT', 'KICK', 'BAN');
    END IF;

   	IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'command_type') THEN
		CREATE TYPE command_type AS ENUM ('PREFIX', 'APPLICATION');
    END IF;
END$$;

-- guild config
CREATE TABLE IF NOT EXISTS config (
	id 					SERIAL UNIQUE,
	guild_id 			BIGINT UNIQUE NOT NULL,
	prefix 				VARCHAR(8) NULL,
	mod_role_id			BIGINT NULL
);

-- moderation values
CREATE TABLE IF NOT EXISTS mod_config (
	id 					SERIAL UNIQUE,
	guild_id 			BIGINT UNIQUE NOT NULL,

	log_channel_id		BIGINT NULL,
	mute_role_id		BIGINT NULL,

	spam_action			security_action NULL,
	spam_count			SMALLINT NOT NULL DEFAULT 8,
	spam_per			SMALLINT NOT NULL DEFAULT 10,

	mention_action		security_action NULL,
	mention_count		SMALLINT NOT NULL DEFAULT 8,
	mention_per			SMALLINT NOT NULL DEFAULT 16,

	raid				BOOLEAN NOT NULL DEFAULT FALSE,
	raid_age			INTERVAL NULL,
	raid_default_avatar	BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS mod_timer (
	id			SERIAL UNIQUE,

	guild_id	BIGINT NOT NULL,
	user_id		BIGINT NOT NULL,
	mod_id		BIGINT NULL,

	event		mod_event_type NOT NULL,

	created_at	TIMESTAMP NOT NULL,
	duration	INTERVAL NULL,

	reason		TEXT NULL,
	userdata	JSON NULL,

	completed	BOOLEAN NOT NULL DEFAULT FALSE
);

-- highlighter languages
CREATE TABLE IF NOT EXISTS highlight_lang (
	id			SERIAL UNIQUE,
	guild_id	BIGINT NOT NULL,
	user_id		BIGINT NOT NULL DEFAULT 0,
	lang		VARCHAR(32) NOT NULL,
	UNIQUE 		(guild_id, user_id)
);

-- starboard config
CREATE TABLE IF NOT EXISTS starboard (
	id			SERIAL UNIQUE,
	guild_id	BIGINT UNIQUE NOT NULL,
	channel_id	BIGINT NULL,
	locked		BOOLEAN NOT NULL DEFAULT FALSE,
	threshold	SMALLINT NULL,
	minimum		SMALLINT NULL
);

-- starmessage
CREATE TABLE IF NOT EXISTS star_msg (
	id				SERIAL UNIQUE,
	guild_id		BIGINT NOT NULL,
	channel_id		BIGINT NOT NULL,
	user_id			BIGINT NOT NULL,
	message_id		BIGINT UNIQUE NOT NULL,
	star_message_id	BIGINT NULL,
	starred_at		TIMESTAMP NOT NULL,
	starrer_id		BIGINT NOT NULL
);

-- starrers
CREATE TABLE IF NOT EXISTS starrers (
	id 			SERIAL UNIQUE,
	star_id		INTEGER NOT NULL REFERENCES star_msg (id) ON DELETE CASCADE,
	user_id		BIGINT NOT NULL,
	UNIQUE 		(star_id, user_id)
);

-- fact list
CREATE TABLE IF NOT EXISTS facts (
	id 			SERIAL UNIQUE,
	content		TEXT NOT NULL
);

-- tag list
CREATE TABLE IF NOT EXISTS tag (
	id			SERIAL UNIQUE,
	name		VARCHAR(32) NOT NULL,
	alias		VARCHAR(32) NULL,
	guild_id	BIGINT NOT NULL,
	user_id		BIGINT NOT NULL,
	uses		INT NOT NULL DEFAULT 0,
	created_at	TIMESTAMP NOT NULL,
	edited_at	TIMESTAMP NULL,
	viewed_at	TIMESTAMP NULL,
	content		VARCHAR(2000) NOT NULL
);

-- command log
CREATE TABLE IF NOT EXISTS log (
	id			SERIAL UNIQUE,
	guild_id	BIGINT NOT NULL,
	channel_id	BIGINT NOT NULL,
	user_id		BIGINT NOT NULL,
	timestamp	TIMESTAMP NOT NULL,
	command		TEXT NOT NULL,
	type		command_type NOT NULL
);

CREATE TABLE IF NOT EXISTS remind (
	id			SERIAL UNIQUE,
	guild_id	BIGINT NOT NULL,
	channel_id	BIGINT NOT NULL,
	user_id		BIGINT NOT NULL,
	message_id	BIGINT NULL,
	made_on		TIMESTAMP NOT NULL,
	remind_on	TIMESTAMP NOT NULL,
	message		TEXT
);

CREATE TABLE IF NOT EXISTS welcome (
	id			SERIAL UNIQUE,
	guild_id	BIGINT UNIQUE NOT NULL,
	channel_id	BIGINT,
	enabled		BOOLEAN NOT NULL DEFAULT TRUE,
	content		VARCHAR(1024)
);

-- docs stuff
CREATE TABLE IF NOT EXISTS role (
	id			SERIAL UNIQUE,
	guild_id	BIGINT UNIQUE NOT NULL,
	channel_id	BIGINT NULL,
	message_ids	BIGINT[8] NOT NULL DEFAULT ARRAY[]::BIGINT[8],
	selectors	INTEGER[8] NOT NULL DEFAULT ARRAY[]::INTEGER[8]
);

CREATE TABLE IF NOT EXISTS role_selector (
	id 			SERIAL UNIQUE,
	guild_id	BIGINT NOT NULL,
	title		VARCHAR(256) NOT NULL,
	description	VARCHAR(1024) NULL,
	icon		VARCHAR(256) NULL,
	inline		BOOLEAN NOT NULL DEFAULT TRUE,
	roles		INTEGER[25] NOT NULL DEFAULT ARRAY[]::INTEGER[25]
);

CREATE TABLE IF NOT EXISTS role_entry (
	id			SERIAL UNIQUE,
	guild_id	BIGINT NOT NULL,
	role_id		BIGINT UNIQUE NOT NULL,
	emoji		VARCHAR(56) NOT NULL,
	name		VARCHAR(199) NOT NULL,
	description	VARCHAR(1024) NOT NULL
);


CREATE TABLE IF NOT EXISTS trivia (
	id				SERIAL UNIQUE,
	guild_id		BIGINT NOT NULL,
	user_id			BIGINT NOT NULL,
	correct_count	INT NOT NULL DEFAULT 0,
	wrong_count		INT NOT NULL DEFAULT 0,
	score			BIGINT NOT NULL DEFAULT 0,
	UNIQUE			(guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS trivia_stats (
	id				SERIAL UNIQUE,
	guild_id		BIGINT NOT NULL,
	user_id			BIGINT NOT NULL,
	timestamp		TIMESTAMP NOT NULL,
	question_hash	BIGINT NOT NULL,
	result			BOOL NOT NULL
);

CREATE TABLE IF NOT EXISTS help_claim (
	guild_id		BIGINT NOT NULL,
	channel_id		BIGINT NOT NULL,
	user_id			BIGINT NOT NULL,
	UNIQUE			(guild_id, channel_id)
);