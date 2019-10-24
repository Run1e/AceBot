import discord
import logging
import parsewhen

from discord.ext import commands
from datetime import datetime, timedelta
from enum import IntEnum

from cogs.mixins import AceMixin
from utils.databasetimer import DatabaseTimer
from utils.string_helpers import shorten
from utils.time import pretty_timedelta, pretty_datetime
from utils.pager import Pager

log = logging.getLogger(__name__)

SUCCESS_EMOJI = '\U00002705'
DEFAULT_REMINDER_MESSAGE = 'Hey, wake up!'
MIN_DELTA = timedelta(minutes=1)
MAX_DELTA = timedelta(days=365 * 10)
MAX_REMINDERS = 9


class RemindPager(Pager):
	async def craft_page(self, e, page, entries):
		now = datetime.utcnow()

		e.set_author(name=self.author.name, icon_url=self.author.avatar_url)
		e.description = 'All your reminders for this server.'

		for _id, guild_id, channel_id, user_id, made_on, remind_on, message in entries:
			delta = remind_on - now

			time_text = pretty_timedelta(delta)
			e.add_field(
				name=f'{_id}: {time_text}',
				value=shorten(message, 256) if message is not None else DEFAULT_REMINDER_MESSAGE,
				inline=False
			)


def dt_factory():
	return datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


class Timescale(IntEnum):
	TIME = 0
	DAY = 1
	MONTH = 2
	YEAR = 3


class CustomEvaluator(parsewhen.eval.Evaluator):
	def __init__(self, *args, **kwargs):
		self.scale = None
		super().__init__(*args, **kwargs)

	def check_scale(self, scale):
		if self.scale is None or scale > self.scale:
			self.scale = scale

	def eval_datetime(self, *args, **kwargs):
		now = datetime.utcnow()
		dt = super().eval_datetime(*args, **kwargs)

		if dt < now:
			if self.scale is Timescale.MONTH:
				dt = dt.replace(year=dt.year + 1)
			if self.scale is Timescale.DAY:
				dt = dt.replace(month=dt.month + 1)

		return dt

	def eval_time(self, *args, **kwargs):
		self.check_scale(Timescale.TIME)
		return super().eval_time(*args, **kwargs)

	def eval_day(self, *args, **kwargs):
		self.check_scale(Timescale.DAY)
		return super().eval_day(*args, **kwargs)

	def eval_date(self, *args, **kwargs):
		self.check_scale(Timescale.DAY)
		return super().eval_date(*args, **kwargs)

	def eval_month(self, *args, **kwargs):
		self.check_scale(Timescale.MONTH)
		return super().eval_month(*args, **kwargs)

	def eval_year(self, *args, **kwargs):
		self.check_scale(Timescale.YEAR)
		return super().eval_year(*args, **kwargs)


class ReminderConverter(commands.Converter):
	async def convert(self, ctx, argument):
		text = list()
		when = None

		try:
			for segment in parsewhen.generate(argument, dates=dt_factory, _evaler=CustomEvaluator):
				if isinstance(segment, str):
					text.append(segment.strip())
				else:
					if when is not None:
						raise commands.CommandError('Multiple times/dates found in reminder string.')

					if isinstance(segment, datetime):
						when = segment
					elif isinstance(segment, timedelta):
						when = datetime.utcnow() + segment
					else:
						raise TypeError('expected datetime or timedelta, got {}'.format(type(segment).__name__))
		except parsewhen.errors.ErrorSource:
			raise commands.CommandError('Failed parsing time.')

		return when, ' '.join(text)


class Reminders(AceMixin, commands.Cog):
	'''Set, view and delete reminders.

	Examples:
	`.remindme in 3 days do the laundry`
	`.remindme next tuesday at 10am call back david`
	`.remindme apply for job 17th of august`
	`.remindme tomorrow take out trash`
	'''

	def __init__(self, bot):
		super().__init__(bot)
		self.timer = DatabaseTimer(self.bot, 'remind', 'remind_on', self.run_reminder)

	async def run_reminder(self, record):
		_id = record.get('id')
		channel_id = record.get('channel_id')
		user_id = record.get('user_id')
		made_on = record.get('made_on')
		message = record.get('message')

		channel = self.bot.get_channel(channel_id)
		user = self.bot.get_user(user_id)

		e = discord.Embed(
			title='Reminder:',
			description=message or DEFAULT_REMINDER_MESSAGE,
			timestamp=made_on
		)

		try:
			if channel is not None:
				await channel.send(content=f'<@{user_id}>', embed=e)
			elif user is not None:
				await user.send(embed=e)
		except discord.HTTPException as exc:
			log.info(f'Failed sending reminder #{_id} for {user.id} - {exc}')

		await self.db.execute('DELETE FROM remind WHERE id=$1', _id)

	@commands.command(aliases=['remind'])
	@commands.bot_has_permissions(add_reactions=True)
	async def remindme(self, ctx, *, when_and_what: ReminderConverter):
		'''Create a new reminder.'''

		when, message = when_and_what
		now = datetime.utcnow()

		if when < now:
			raise commands.CommandError('Specified time is in the past.')

		if when - now > MAX_DELTA:
			raise commands.CommandError('Sorry, can\'t remind in more than a year in the future.')

		if message is not None and len(message) > 512:
			raise commands.CommandError('Sorry, keep the message below 1024 characters!')

		count = await self.db.fetchval('SELECT COUNT(id) FROM remind WHERE user_id=$1', ctx.author.id)
		if count > MAX_REMINDERS:
			raise commands.CommandError(f'Sorry, you can\'t have more than {MAX_REMINDERS} active reminders at once.')

		await self.db.execute(
			'INSERT INTO remind (guild_id, channel_id, user_id, made_on, remind_on, message) VALUES ($1, $2, $3, $4, $5, $6)',
			ctx.guild.id, ctx.channel.id, ctx.author.id, now, when, message
		)

		self.timer.maybe_restart(when)

		#await ctx.message.add_reaction(SUCCESS_EMOJI)
		await ctx.send('You will be reminded the {} UTC'.format(pretty_datetime(when)))

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def reminders(self, ctx):
		'''List your reminders in this guild.'''

		res = await self.db.fetch(
			'SELECT * FROM remind WHERE guild_id=$1 AND user_id=$2 ORDER BY id DESC',
			ctx.guild.id, ctx.author.id
		)

		if not len(res):
			raise commands.CommandError('Couldn\'t find any reminders.')

		p = RemindPager(ctx, res, per_page=3)
		await p.go()

	@commands.command()
	async def delreminder(self, ctx, *, reminder_id: int):
		'''Delete a reminder. Must be your own reminder.'''

		res = await self.db.execute(
			'DELETE FROM remind WHERE id=$1 AND guild_id=$2 AND user_id=$3',
			reminder_id, ctx.guild.id, ctx.author.id
		)

		if res == 'DELETE 1':
			await ctx.send('Reminder deleted.')
			self.timer.restart_if(lambda record: record.get('id') == reminder_id)
		else:
			raise commands.CommandError('Reminder not found, or you do not own it.')


def setup(bot):
	bot.add_cog(Reminders(bot))
