import asyncio
import disnake
import asyncpg
import logging

from datetime import datetime, timedelta

from utils.time import pretty_timedelta


log = logging.getLogger(__name__)


class DatabaseTimer:
	MAX_SLEEP = timedelta(days=40)

	def __init__(self, bot, event_name):
		self.bot = bot
		self.event_name = event_name

		self.record = None
		self.task = self.start_task()

	def start_task(self):
		return self.bot.loop.create_task(self.dispatch())

	def restart_task(self):
		self.task.cancel()
		self.task = self.start_task()

	async def dispatch(self):
		try:
			while True:
				# fetch next record
				record = await self.get_record()

				# if none was found, sleep for 40 days and check again
				if record is None:
					log.debug('No record found for %s, sleeping', self.event_name)
					await asyncio.sleep(self.MAX_SLEEP.total_seconds())
					continue

				# we are now with this record
				self.record = record

				# get datetime again in case query took a lot of time
				now = datetime.utcnow()
				then = self.when(record)
				dt = then - now

				# if the next record is in the future, sleep until it should be invoked
				if now < then:
					log.debug('%s dispatching in %s', self.event_name, pretty_timedelta(then - now))
					await asyncio.sleep(dt.total_seconds())

				await self.cleanup_record(record)
				self.record = None

				log.debug('Dispatching event %s', self.event_name)

				# run it
				self.bot.dispatch(self.event_name, record)

		except (disnake.ConnectionClosed, asyncpg.PostgresConnectionError) as e:
			# if anything happened, sleep for 15 seconds then attempt a restart
			log.warning('DatabaseTimer got exception %s: attempting restart in 15 seconds', str(e))

			await asyncio.sleep(15)
			self.restart_task()

	async def get_record(self):
		raise NotImplementedError

	async def cleanup_record(self, record):
		raise NotImplementedError

	def when(self, record):
		raise NotImplementedError

	def maybe_restart(self, dt):
		if self.record is None:
			self.restart_task()

		elif dt < self.when(self.record):
			self.restart_task()

	def restart_if(self, pred):
		if self.record is None or pred(self.record):
			self.restart_task()


class ColumnTimer(DatabaseTimer):
	def __init__(self, bot, event_name, table, column):
		super().__init__(bot, event_name)
		self.table = table
		self.column = column

	async def get_record(self):
		return await self.bot.db.fetchrow(
			'SELECT * FROM {0} WHERE {1} < $1 AND {1} IS NOT NULL ORDER BY {1} LIMIT 1'.format(self.table, self.column),
			datetime.utcnow() + self.MAX_SLEEP
		)

	async def cleanup_record(self, record):
		await self.bot.db.execute('DELETE FROM {0} WHERE id=$1'.format(self.table), record.get('id'))

	def when(self, record):
		return record.get(self.column)
