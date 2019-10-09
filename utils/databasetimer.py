import asyncio
import discord
import asyncpg

from datetime import datetime, timedelta

MAX_SLEEP = timedelta(days=40)


class DatabaseTimer:
	def __init__(self, bot, table, column, callback):
		self.bot = bot
		self.table = table
		self.column = column
		self.callback = callback
		self.query = 'SELECT * FROM {0} WHERE {1} < $1 AND {1} IS NOT NULL ORDER BY {1} LIMIT 1'.format(table, column)

		self.record = None
		self.task = self.start_task()

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
				record = await self.bot.db.fetchrow(self.query, datetime.utcnow() + MAX_SLEEP)
				self.record = record

				if record is None:
					await asyncio.sleep(MAX_SLEEP.total_seconds())
					continue

				now = datetime.utcnow()
				then = record.get(self.column)

				if now < then:
					await asyncio.sleep((then - now).total_seconds())

				self.record = None

				try:
					await self.callback(record)
				except Exception:
					pass

		except (discord.ConnectionClosed, asyncpg.PostgresConnectionError):
			self.restart_task()

	def maybe_restart(self, time):
		next_at = self.next_at
		if next_at is None or time < next_at:
			self.restart_task()

	def restart_if(self, pred):
		if self.record is None or pred(self.record):
			self.restart_task()
