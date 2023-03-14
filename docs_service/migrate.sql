CREATE TABLE IF NOT EXISTS docs_entry (
	id			SERIAL UNIQUE,
    v           SMALLINT NOT NULL,
    name        TEXT NOT NULL,
    page        TEXT NOT NULL,
    fragment    TEXT NULL,
    content     TEXT NULL,
    syntax      TEXT NULL,
    version     TEXT NULL,
    parents     INTEGER[] NULL
);

CREATE TABLE IF NOT EXISTS docs_name (
	id			SERIAL UNIQUE,
    v           SMALLINT NOT NULL,
	docs_id		INT REFERENCES docs_entry (id) NOT NULL,
	name		TEXT UNIQUE NOT NULL
);
