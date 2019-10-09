import discord
import logging

from discord.ext import commands
from datetime import datetime, timedelta

from cogs.mixins import AceMixin
from utils.databasetimer import DatabaseTimer
from utils.converters import TimeMultConverter, TimeDeltaConverter
from utils.string_helpers import shorten
from utils.time import pretty_timedelta
from utils.pager import Pager

log = logging.getLogger(__name__)

SUCCESS_EMOJI = '\U00002705'
DEFAULT_REMINDER_MESSAGE = 'Hey, wake up!'
MIN_DELTA = timedelta(minutes=1)
MAX_DELTA = timedelta(days=365)
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


class Reminders(AceMixin, commands.Cog):
	'''Set, view and delete reminders.

	Valid time units are: `minutes`, `hours`, `days` or `weeks`
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
			log.info(f'Failed sending reminder #{id} for {user.id} - {exc}')

		await self.db.execute('DELETE FROM remind WHERE id=$1', _id)

	@commands.command()
	@commands.bot_has_permissions(add_reactions=True)
	async def remindme(self, ctx, amount: TimeMultConverter, unit: TimeDeltaConverter, *, message=None):
		'''Create a new reminder.'''

		now = datetime.utcnow()
		delta = unit * amount
		remind_on = now + delta

		if delta > MAX_DELTA:
			raise commands.CommandError('Sorry, can\'t remind in more than a year in the future.')

		if message is not None and len(message) > 512:
			raise commands.CommandError('Sorry, keep the message below 1024 characters!')

		count = await self.db.fetchval('SELECT COUNT(id) FROM remind WHERE user_id=$1', ctx.author.id)
		if count > MAX_REMINDERS:
			raise commands.CommandError(f'Sorry, you can\'t have more than {MAX_REMINDERS} active reminders at once.')

		await self.db.execute(
			'INSERT INTO remind (guild_id, channel_id, user_id, made_on, remind_on, message) VALUES ($1, $2, $3, $4, $5, $6)',
			ctx.guild.id, ctx.channel.id, ctx.author.id, now, remind_on, message
		)

		self.timer.maybe_restart(remind_on)

		await ctx.message.add_reaction(SUCCESS_EMOJI)

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
