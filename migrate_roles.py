import asyncpg
import asyncio

from config import DB_BIND


CREATE_STR = '''
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
'''


async def main():
	c = await asyncpg.connect(DB_BIND)

	orig_role = await c.fetch('SELECT * FROM role')
	orig_role_entry = await c.fetch('SELECT * FROM role_entry')

	# delete role and role_entry

	await c.execute('DROP TABLE role')
	await c.execute('DROP TABLE role_entry')

	await c.execute(CREATE_STR)

	# create all three new tables

	print(orig_role)
	print(orig_role_entry)

	for role in orig_role:
		if role.get('channel_id') is None:
			print('skipping {}'.format(role.get('id')))
			continue

		role_ids = list()

		for role_entry in orig_role_entry:
			if role_entry.get('id') in role.get('roles'):
				_id = await c.fetchval(
					'INSERT INTO role_entry (guild_id, role_id, emoji, name, description) VALUES ($1, $2, $3, $4, $5) RETURNING id',
					role.get('guild_id'), role_entry.get('role_id'), role_entry.get('emoji'), role_entry.get('name'),
					role_entry.get('description')
				)

				role_ids.append(_id)

		# all roles added, now create selector

		selector_id = await c.fetchval(
			'INSERT INTO role_selector (guild_id, title, inline, roles) VALUES ($1, $2, $3, $4) RETURNING id',
			role.get('guild_id'), 'Role Selector', role.get('inline'), role_ids
		)

		await c.fetchval(
			'INSERT INTO role (guild_id, channel_id, message_ids, selectors) VALUES ($1, $2, $3, $4)',
			role.get('guild_id'), role.get('channel_id'), [role.get('message_id')], [selector_id]
		)




if __name__ == '__main__':
	asyncio.run(main())
