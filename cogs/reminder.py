import discord, asyncio
from discord.ext import commands

from utils.database import db, RemindMeEntry
from utils.time import pretty_seconds
from utils.pager import Pager
from utils.string_manip import shorten
from cogs.base import TogglableCogMixin
from datetime import datetime, timedelta

SUCCESS_EMOJI = '\U00002705'
CHECK_EVERY = 60
DEFAULT_REMINDER_MESSAGE = 'Hey, wake up!'
MAX_DELTA = timedelta(days=365)
MAX_REMINDERS = 16


class TimeUnit(commands.Converter):
	async def convert(self, ctx, unit):
		unit = unit.lower()

		if unit in ('min', 'mins', 'minute', 'minutes'):
			seconds = 60
		elif unit in('hr', 'hrs', 'hour', 'hours'):
			seconds = 60 * 60
		elif unit in ('day', 'days'):
			seconds = 60 * 60 * 24
		else:
			raise commands.BadArgument('Unknown time type.')

		return seconds


class RemindPager(Pager):
	async def craft_page(self, e, page, entries):
		now = datetime.utcnow()

		e.set_author(name=self.member.name, icon_url=self.member.avatar_url)
		e.description = 'All your reminders for this server.'

		for id, guild_id, channel_id, user_id, remind_on, made_on, message in entries:
			delta = (remind_on - now).total_seconds()
			time_text = 'Soon...' if delta < 15 else pretty_seconds(delta)
			e.add_field(
				name=f'({id}): {time_text}',
				value=shorten(message, 256, 2) if message is not None else DEFAULT_REMINDER_MESSAGE,
				inline=False
			)


class Reminders(TogglableCogMixin):
	'''Set, view and delete reminders.'''

	def __init__(self, bot):
		super().__init__(bot)
		self.bot.loop.create_task(self.check_reminders())

	async def __local_check(self, ctx):
		return await self._is_used(ctx)

	@commands.command()
	async def reminders(self, ctx):
		'''List your reminders in this guild.'''

		res = await db.all(
			'SELECT * FROM reminder WHERE guild_id=$1 AND user_id=$2 ORDER BY id DESC',
			ctx.guild.id, ctx.author.id
		)

		if not len(res):
			raise commands.CommandError('Couldn\'t find any reminders.')

		p = RemindPager(ctx, res, per_page=6)
		p.member = ctx.author
		await p.go()

	@commands.command()
	async def delreminder(self, ctx, id: int):
		'''Delete a reminder.'''

		res = await db.first(
			'SELECT * FROM reminder WHERE id=$1 AND user_id=$2 AND guild_id=$3',
			id, ctx.author.id, ctx.guild.id
		)

		if res is None:
			raise commands.CommandError('Couldn\'t find reminder or you don\'t own it.')

		await db.scalar('DELETE FROM reminder WHERE id=$1', res.id)
		await ctx.send('Reminder deleted.')

	@commands.command(aliases=['reminder', 'remind'])
	async def remindme(self, ctx, amount: float, unit: TimeUnit, *, message = None):
		'''Create a new reminder.'''

		if amount < 1.0:
			raise commands.CommandError('Sorry, please use an amount more than 1.0')

		seconds = int(amount * unit)

		now = datetime.utcnow()
		delta = timedelta(seconds=seconds)

		if delta > MAX_DELTA:
			raise commands.CommandError('Sorry. Can\'t remind in more than a year!')

		if message is not None and len(message) > 1024:
			raise commands.CommandError('Sorry, keep the message below 1024 characters!')

		count = await db.scalar('SELECT COUNT(id) FROM reminder WHERE user_id=$1', ctx.author.id)
		if count > MAX_REMINDERS:
			raise commands.CommandError(f'Sorry, you can\'t have more than {MAX_REMINDERS} active reminders at once.')

		# Add the reminder to the DB
		await RemindMeEntry.create(
			guild_id=ctx.guild.id,
			channel_id=ctx.channel.id,
			user_id=ctx.author.id,
			made_on=now,
			remind_on=now + delta,
			message=message
		)

		await ctx.message.add_reaction(SUCCESS_EMOJI)

	async def check_reminders(self):
		while True:
			await asyncio.sleep(CHECK_EVERY)

			res = await db.all('SELECT * FROM reminder WHERE remind_on<=$1', datetime.utcnow())

			for id, guild_id, channel_id, user_id, remind_on, made_on, message in res:
				# If it is time to send the reminder, then get the guild it was sent in so we can get the user to send it to

				channel = self.bot.get_channel(channel_id)
				user = self.bot.get_user(user_id)

				# If there is no reminder message, use the default one
				if message is None:
					message = DEFAULT_REMINDER_MESSAGE

				e = discord.Embed(
					title='Reminder:',
					description=message
				)

				e.timestamp = made_on

				# Encapsulate the reminder message in the prefix/suffix, and send it to the user
				try:
					if channel is not None:
						await channel.send(content=f'<@{user_id}>', embed=e)
					elif user is not None:
						await user.send(embed=e)
				except discord.HTTPException:
					pass

				# Get the record we just sent the message for, and delete it so it isn't sent again
				await db.scalar('DELETE FROM reminder WHERE id=$1', id)


def setup(bot):
	bot.add_cog(Reminders(bot))
