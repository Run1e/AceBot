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

