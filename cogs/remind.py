import discord
import logging
import parsedatetime

from discord.ext import commands
from datetime import datetime, timedelta
from enum import IntEnum

from cogs.mixins import AceMixin
from utils.databasetimer import ColumnTimer
from utils.string import shorten, po
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


class ReminderConverter(commands.Converter):
	NO_DT_FOUND = commands.CommandError('No time/date found in input.')

	async def convert(self, ctx, argument):

		cal = parsedatetime.Calendar()
		now = datetime.utcnow()

		try:
			when, when_type = cal.parseDT(argument, now)
		except Exception:
			raise self.NO_DT_FOUND

		if when_type == 0:
			raise self.NO_DT_FOUND

		return now, when, argument


class Reminders(AceMixin, commands.Cog):
	'''Set, view, and delete reminders.

	Examples:
	`.remindme in 3 days do the laundry`
	`.remindme call back david in 10 minutes`
	`.remindme apply for job 17th of august`
	`.remindme tomorrow take out trash`

	Absolute dates/times are in UTC.
	'''

	def __init__(self, bot):
		super().__init__(bot)
		self.timer = ColumnTimer(self.bot, 'reminder_complete', table='remind', column='remind_on')

	@commands.Cog.listener()
	async def on_reminder_complete(self, record):
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

	@commands.command(aliases=['remind'])
	@commands.bot_has_permissions(add_reactions=True)
	async def remindme(self, ctx, *, when_and_what: ReminderConverter):
		'''Create a new reminder.'''

		now, when, message = when_and_what

		if when < now:
			raise commands.CommandError('Specified time is in the past.')

		if when - now > MAX_DELTA:
			raise commands.CommandError('Sorry, can\'t remind in more than a year in the future.')

		if message is not None and len(message) > 1024:
			raise commands.CommandError('Sorry, keep the message below 1024 characters!')

		count = await self.db.fetchval('SELECT COUNT(id) FROM remind WHERE user_id=$1', ctx.author.id)
		if count > MAX_REMINDERS:
			raise commands.CommandError(f'Sorry, you can\'t have more than {MAX_REMINDERS} active reminders at once.')

		await self.db.execute(
			'INSERT INTO remind (guild_id, channel_id, user_id, made_on, remind_on, message) VALUES ($1, $2, $3, $4, $5, $6)',
			ctx.guild.id, ctx.channel.id, ctx.author.id, now, when, message
		)

		self.timer.maybe_restart(when)

		remind_in = when - now
		remind_in += timedelta(microseconds=1000000 - (remind_in.microseconds % 1000000))

		await ctx.send('You will be reminded in {}.'.format(pretty_timedelta(remind_in)))

		log.info('{} set a reminder for {}.'.format(po(ctx.author), pretty_datetime(when)))

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
