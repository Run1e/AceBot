import asyncpg
import asyncio

from asyncpg.exceptions import UniqueViolationError

from config import DB_BIND


async def main():
	target = await asyncpg.connect(DB_BIND)
	origin = await asyncpg.connect('postgresql://ace:password@192.168.1.3/acebot')

	print('reminders...')

	# reminders
	for row in await origin.fetch('SELECT * FROM reminder'):
		try:
			await target.execute(
				'INSERT INTO remind (guild_id, channel_id, user_id, made_on, remind_on, message) VALUES ($1, $2, $3, $4, $5, $6)',
				row.get('guild_id'), row.get('channel_id'), row.get('user_id'), row.get('made_on'), row.get('remind_on'), row.get('message')
			)
			print('remind: guild {} channel {} user {}'.format(row.get('guild_id'), row.get('channel_id'), row.get('user_id')))
		except UniqueViolationError:
			pass

	print('starboards...')

	# starboard settings
	for row in await origin.fetch('SELECT * FROM starguild'):
		try:
			await target.execute(
				'INSERT INTO starboard (guild_id, channel_id) VALUES ($1, $2)',
				row.get('guild_id'), row.get('channel_id')
			)
			print('starboard: guild {} channel {}'.format(row.get('guild_id'), row.get('channel_id')))
		except UniqueViolationError:
			pass

	print('starred messages...')

	# starboard messages and starrers
	for row in await origin.fetch('SELECT * FROM starmessage'):
		try:
			nid = await target.fetchval(
				'INSERT INTO star_msg (guild_id, channel_id, user_id, message_id, star_message_id, starred_at, starrer_id) VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id',
				row.get('guild_id'), row.get('channel_id'), row.get('author_id'), row.get('message_id'), row.get('star_message_id'), row.get('starred_at'), row.get('starrer_id')
			)
			starrers = await origin.fetch('SELECT * FROM starrers WHERE star_id=$1', row.get('id'))
			for star_row in starrers:
				await target.execute(
					'INSERT INTO starrers (star_id, user_id) VALUES ($1, $2)',
					nid, star_row.get('user_id')
				)
			print('star_msg: id {} with {} starrers'.format(nid, len(starrers)))
		except UniqueViolationError:
			pass

	print('tags...')

	# tags
	for row in await origin.fetch('SELECT * FROM tag'):
		try:
			await target.execute(
				'INSERT INTO tag (name, alias, guild_id, user_id, uses, created_at, edited_at, content) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)',
				row.get('name'), row.get('alias'), row.get('guild_id'), row.get('owner_id'), row.get('uses'),
				row.get('created_at'), row.get('edited_at'), row.get('content')
			)
			print('tag: name {} guild {}'.format(row.get('name'), row.get('guild_id')))
		except UniqueViolationError:
			pass

	print('highlight langs...')

	# highlight langs
	for row in await origin.fetch('SELECT * FROM highlight'):
		uid = row.get('user_id')
		try:
			await target.execute(
				'INSERT INTO highlight_lang (guild_id, user_id, lang) VALUES ($1, $2, $3)',
				row.get('guild_id'), 0 if uid is None else uid, row.get('language')
			)
			print('hl lang: guild {} user {} lang {}'.format(row.get('guild_id'), uid, row.get('language')))
		except UniqueViolationError:
			pass

	print('welcome messages...')

	# welcome messages
	for row in await origin.fetch('SELECT * FROM welcome'):
		try:
			await target.execute(
				'INSERT INTO welcome (guild_id, channel_id, content) VALUES ($1, $2, $3)',
				row.get('guild_id'), row.get('channel_id'), row.get('content')
			)
			print('welcome: guild {} channel {}'.format(row.get('guild_id'), row.get('channel_id')))
		except UniqueViolationError:
			pass

	print('seen...')

	# seen
	for row in await origin.fetch('SELECT * FROM seen'):
		try:
			await target.execute(
				'INSERT INTO seen (guild_id, user_id, seen) VALUES ($1, $2, $3)',
				row.get('guild_id'), row.get('user_id'), row.get('seen')
			)
		except UniqueViolationError:
			pass

	print('logs...')

	# logs
	for row in await origin.fetch('SELECT * FROM log'):
		try:
			await target.execute(
				'INSERT INTO log (guild_id, channel_id, user_id, timestamp, command) VALUES ($1, $2, $3, $4, $5)',
				row.get('guild_id'), row.get('channel_id'), row.get('author_id'), row.get('date'), row.get('command')
			)
		except UniqueViolationError:
			pass

	print('finished!')


if __name__ == '__main__':
	asyncio.run(main())


"""
                                        Table "public.log"
   Column   |            Type             | Collation | Nullable |             Default
------------+-----------------------------+-----------+----------+---------------------------------
 id         | integer                     |           | not null | nextval('log_id_seq'::regclass)
 guild_id   | bigint                      |           |          |
 channel_id | bigint                      |           |          |
 author_id  | bigint                      |           |          |
 date       | timestamp without time zone |           |          |
 command    | character varying           |           |          |
Indexes:
    "log_pkey" PRIMARY KEY, btree (id)

                                        Table "public.log"
   Column   |            Type             | Collation | Nullable |             Default
------------+-----------------------------+-----------+----------+---------------------------------
 id         | integer                     |           | not null | nextval('log_id_seq'::regclass)
 guild_id   | bigint                      |           | not null |
 channel_id | bigint                      |           | not null |
 user_id    | bigint                      |           | not null |
 timestamp  | timestamp without time zone |           | not null |
 command    | text                        |           | not null |
Indexes:
    "log_id_key" UNIQUE CONSTRAINT, btree (id)
"""

"""
                                        Table "public.reminder"
   Column   |            Type             | Collation | Nullable |               Default
------------+-----------------------------+-----------+----------+--------------------------------------
 id         | integer                     |           | not null | nextval('reminder_id_seq'::regclass)
 guild_id   | bigint                      |           |          |
 channel_id | bigint                      |           |          |
 user_id    | bigint                      |           |          |
 remind_on  | timestamp without time zone |           |          |
 made_on    | timestamp without time zone |           |          |
 message    | character varying           |           |          |
Indexes:
    "reminder_pkey" PRIMARY KEY, btree (id)

                                        Table "public.remind"
   Column   |            Type             | Collation | Nullable |              Default
------------+-----------------------------+-----------+----------+------------------------------------
 id         | integer                     |           | not null | nextval('remind_id_seq'::regclass)
 guild_id   | bigint                      |           | not null |
 channel_id | bigint                      |           | not null |
 user_id    | bigint                      |           | not null |
 made_on    | timestamp without time zone |           | not null |
 remind_on  | timestamp without time zone |           | not null |
 message    | text                        |           |          |
Indexes:
    "remind_id_key" UNIQUE CONSTRAINT, btree (id)
"""


"""

                           Table "public.seen"
  Column  |            Type             | Collation | Nullable | Default
----------+-----------------------------+-----------+----------+---------
 guild_id | bigint                      |           | not null |
 user_id  | bigint                      |           | not null |
 seen     | timestamp without time zone |           |          |
Indexes:
    "seen_pkey" PRIMARY KEY, btree (guild_id, user_id)

                                       Table "public.seen"
  Column  |            Type             | Collation | Nullable |             Default
----------+-----------------------------+-----------+----------+----------------------------------
 id       | integer                     |           | not null | nextval('seen_id_seq'::regclass)
 guild_id | bigint                      |           | not null |
 user_id  | bigint                      |           | not null |
 seen     | timestamp without time zone |           | not null |
Indexes:
    "seen_guild_id_user_id_key" UNIQUE CONSTRAINT, btree (guild_id, user_id)
    "seen_id_key" UNIQUE CONSTRAINT, btree (id)
"""


"""
                              Table "public.starguild"
   Column   |  Type   | Collation | Nullable |                Default
------------+---------+-----------+----------+---------------------------------------
 id         | integer |           | not null | nextval('starguild_id_seq'::regclass)
 guild_id   | bigint  |           |          |
 channel_id | bigint  |           |          |
Indexes:
    "starguild_pkey" PRIMARY KEY, btree (id)

                               Table "public.starboard"
   Column   |   Type   | Collation | Nullable |                Default
------------+----------+-----------+----------+---------------------------------------
 id         | integer  |           | not null | nextval('starboard_id_seq'::regclass)
 guild_id   | bigint   |           | not null |
 channel_id | bigint   |           |          |
 locked     | boolean  |           | not null | false
 threshold  | smallint |           | not null | '3'::smallint
 max_age    | interval |           | not null | '7 days'::interval
Indexes:
    "starboard_id_key" UNIQUE CONSTRAINT, btree (id)
"""

"""
                             Table "public.starrers"
 Column  |  Type   | Collation | Nullable |               Default
---------+---------+-----------+----------+--------------------------------------
 id      | integer |           | not null | nextval('starrers_id_seq'::regclass)
 user_id | bigint  |           |          |
 star_id | integer |           |          |
Indexes:
    "starrers_pkey" PRIMARY KEY, btree (id)
Foreign-key constraints:
    "starrers_star_id_fkey" FOREIGN KEY (star_id) REFERENCES starmessage(id)

                             Table "public.starrers"
 Column  |  Type   | Collation | Nullable |               Default
---------+---------+-----------+----------+--------------------------------------
 id      | integer |           | not null | nextval('starrers_id_seq'::regclass)
 star_id | integer |           |          |
 user_id | bigint  |           | not null |
Indexes:
    "starrers_id_key" UNIQUE CONSTRAINT, btree (id)
    "starrers_star_id_user_id_key" UNIQUE CONSTRAINT, btree (star_id, user_id)
Foreign-key constraints:
    "starrers_star_id_fkey" FOREIGN KEY (star_id) REFERENCES star_msg(id)
"""

"""
                                           Table "public.starmessage"
     Column      |            Type             | Collation | Nullable |                 Default
-----------------+-----------------------------+-----------+----------+-----------------------------------------
 id              | integer                     |           | not null | nextval('starmessage_id_seq'::regclass)
 message_id      | bigint                      |           |          |
 channel_id      | bigint                      |           |          |
 star_message_id | bigint                      |           |          |
 starrer_id      | bigint                      |           |          |
 starred_at      | timestamp without time zone |           |          |
 guild_id        | bigint                      |           |          |
 author_id       | bigint                      |           |          |
Indexes:
    "starmessage_pkey" PRIMARY KEY, btree (id)
Referenced by:
    TABLE "starrers" CONSTRAINT "starrers_star_id_fkey" FOREIGN KEY (star_id) REFERENCES starmessage(id)

                                           Table "public.star_msg"
     Column      |            Type             | Collation | Nullable |               Default
-----------------+-----------------------------+-----------+----------+--------------------------------------
 id              | integer                     |           | not null | nextval('star_msg_id_seq'::regclass)
 guild_id        | bigint                      |           | not null |
 channel_id      | bigint                      |           | not null |
 user_id         | bigint                      |           | not null |
 message_id      | bigint                      |           | not null |
 star_message_id | bigint                      |           | not null |
 starred_at      | timestamp without time zone |           | not null |
 starrer_id      | bigint                      |           | not null |
Indexes:
    "star_msg_id_key" UNIQUE CONSTRAINT, btree (id)
    "star_msg_message_id_key" UNIQUE CONSTRAINT, btree (message_id)
Referenced by:
    TABLE "starrers" CONSTRAINT "starrers_star_id_fkey" FOREIGN KEY (star_id) REFERENCES star_msg(id)
"""