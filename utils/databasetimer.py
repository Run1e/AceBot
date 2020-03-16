import asyncio
import discord
import asyncpg
import logging

from datetime import datetime, timedelta

from utils.time import pretty_timedelta


log = logging.getLogger(__name__)

MAX_SLEEP = timedelta(days=40)


class DatabaseTimer:
	def __init__(self, bot, table, column, event_name):
		self.bot = bot
		self.table = table
		self.column = column
		self.event_name = event_name
		self.query = 'SELECT * FROM {0} WHERE {1} < $1 AND {1} IS NOT NULL ORDER BY {1} LIMIT 1'.format(table, column)

		self.record = None
		self.task = self.start_task()

		log.debug('Creating DatabaseTimer for table "{0}" on column "{1}"'.format(table, column))

	def start_task(self):
		return self.bot.loop.create_task(self.dispatch())

	def restart_task(self):
		self.task.cancel()
		self.task = self.start_task()

	@property
	def next_at(self):
		return None if self.record is None else self.record.get(self.column)

	async def dispatch(self):
		try:
			while True:
				# fetch next record (if one exists within 40 days from now)
				record = await self.bot.db.fetchrow(self.query, datetime.utcnow() + MAX_SLEEP)
				self.record = record

				# if none was found, sleep for 40 days and check again
				if record is None:
					log.debug('No record found for "{}", sleeping'.format(self.table))
					await asyncio.sleep(MAX_SLEEP.total_seconds())
					continue

				# get datetime again in case query took a lot of time
				now = datetime.utcnow()
				then = record.get(self.column)
				dt = then - now

				# if the next record is in the future, sleep until it should be invoked
				if now < then:
					log.debug('{} dispatching in {}'.format(self.event_name, pretty_timedelta(then - now)))
					await asyncio.sleep(dt.total_seconds())

				self.record = None

				# delete row before dispatching event
				await self.bot.db.execute('DELETE FROM {} WHERE id={}'.format(self.table, record.get('id')))

				log.debug('Dispatching event {}'.format(self.event_name))

				# run it
				self.bot.dispatch(self.event_name, record)

		except (discord.ConnectionClosed, asyncpg.PostgresConnectionError) as e:
			# if anything happened, sleep for 15 seconds then attempt a restart
			log.warning('DatabaseTimer got exception {}: attempting restart in 15 seconds'.format(str(e)))

			await asyncio.sleep(15)
			self.restart_task()

	def maybe_restart(self, time):
		next_at = self.next_at
		if next_at is None or time < next_at:
			self.restart_task()

	def restart_if(self, pred):
		if self.record is None or pred(self.record):
			self.restart_task()
