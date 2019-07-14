import discord
import inspect

from discord.ext import commands
from datetime import datetime, timedelta

from config import FEEDBK_CHANNEL

from cogs.mixins import AceMixin
from utils.time import pretty_timedelta

MEDALS = (
	'\N{FIRST PLACE MEDAL}',
	'\N{SECOND PLACE MEDAL}',
	'\N{THIRD PLACE MEDAL}',
	'\N{SPORTS MEDAL}',
	'\N{SPORTS MEDAL}'
)


class Meta(AceMixin, commands.Cog):
	'''Commands about the bot itself.'''

	@commands.command()
	async def uptime(self, ctx):
		'''Time since last bot restart.'''

		await ctx.send(
			f'It has been {pretty_timedelta(datetime.utcnow() - self.bot.startup_time)} '
			'since the last bot restart.'
		)

	@commands.command(aliases=['join'])
	async def invite(self, ctx):
		'''Get bot invite link.'''

		await ctx.send(self.bot.invite_link)

	@commands.command()
	async def dbl(self, ctx):
		'''Get link to discordbots.org bot page.'''

		await ctx.send('https://discordbots.org/bot/367977994486022146')

	@commands.command(aliases=['source'])
	async def code(self, ctx, *, command: str = None):
		'''Show command code or get GitHub repo link.'''

		if command is None:
			await ctx.send('https://github.com/Run1e/AceBot')
			return

		command = self.bot.get_command(command)

		if command is None or command.hidden:
			raise commands.CommandError('Couldn\'t find command.')

		code = '\n'.join(line[1:] for line in inspect.getsource(command.callback).splitlines())
		code = code.replace('`', '\u200b`')
		await ctx.send(f'```py\n{code}\n```')

	@commands.command()
	async def support(self, ctx):
		'''Get link to support server.'''
		await ctx.send(self.bot._support_link)

	@commands.command(aliases=['fb'])
	@commands.cooldown(rate=1, per=60.0, type=commands.BucketType.user)
	async def feedback(self, ctx, *, feedback: str):
		'''Give me some feedback about the bot!'''

		e = discord.Embed(title='Feedback', description=feedback)

		e.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)

		e.add_field(name='Guild', value=f'{ctx.guild.name} ({ctx.guild.id})')
		e.set_footer(text=f'Author ID: {ctx.author.id}')

		dest = self.bot.get_channel(FEEDBK_CHANNEL)

		if dest is None:
			raise commands.CommandError('Feedback not sent. Feedback channel was not found, or not set up.')

		await dest.send(embed=e)
		await ctx.send('Feedback sent. Thanks for helping improve the bot!')

	@commands.command(hidden=True)
	async def hello(self, ctx):
		await ctx.send(f'Hello {ctx.author.mention}!')

	@commands.command()
	async def stats(self, ctx, member: discord.Member = None):
		'''Show bot or user command stats.'''

		def create_list(cmds, members=None):
			value = ''
			for index, cmd in enumerate(cmds):
				value += f'\n{MEDALS[index]} {members[index] if members else cmd[1]} ({cmd[0]} uses)'

			if not len(value):
				return 'None so far!'

			return value[1:]

		now = datetime.utcnow() - timedelta(days=1)

		e = discord.Embed()

		if member is None:
			# guild stats

			e.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)

			total_uses = await self.db.fetchval('SELECT COUNT(id) FROM log WHERE guild_id=$1', ctx.guild.id)

			commands_today = await self.db.fetch(
				'SELECT COUNT(id), command FROM log WHERE guild_id=$1 AND timestamp > $2 GROUP BY command '
				'ORDER BY COUNT DESC LIMIT 5', ctx.guild.id, now
			)

			commands_alltime = await self.db.fetch(
				'SELECT COUNT(id), command FROM log WHERE guild_id=$1 GROUP BY command ORDER BY COUNT DESC LIMIT 5',
				ctx.guild.id
			)

			users_today = await self.db.fetch(
				'SELECT COUNT(id), user_id FROM log WHERE guild_id=$1 AND timestamp > $2 GROUP BY user_id '
				'ORDER BY COUNT DESC LIMIT 5', ctx.guild.id, now
			)

			users_alltime = await self.db.fetch(
				'SELECT COUNT(id), user_id FROM log WHERE guild_id=$1 GROUP BY user_id '
				'ORDER BY COUNT DESC LIMIT 5', ctx.guild.id
			)

			e.add_field(name='Top Commands', value=create_list(commands_alltime))
			e.add_field(name='Top Commands Today', value=create_list(commands_today))

			e.add_field(
				name='Top Users',
				value=create_list(users_alltime, [f'<@{user_id}>' for _, user_id in users_alltime])
			)

			e.add_field(
				name='Top Users Today',
				value=create_list(users_today, [f'<@{user_id}>' for _, user_id in users_today])
			)

		else:
			# user stats

			e.set_author(name=member.name, icon_url=member.avatar_url)

			total_uses = await self.db.fetchval(
				'SELECT COUNT(id) FROM log WHERE guild_id=$1 AND user_id=$2',
				ctx.guild.id, ctx.author.id
			)

			commands_alltime = await self.db.fetch(
				'SELECT COUNT(id), command FROM log WHERE guild_id=$1 AND user_id=$2 GROUP BY command '
				'ORDER BY COUNT DESC LIMIT 5', ctx.guild.id, ctx.author.id
			)

			commands_today = await self.db.fetch(
				'SELECT COUNT(id), command FROM log WHERE guild_id=$1 AND user_id=$2 AND timestamp > $3 '
				'GROUP BY command ORDER BY COUNT DESC LIMIT 5', ctx.guild.id, ctx.author.id, now
			)

			e.add_field(name='Top Commands', value=create_list(commands_alltime))
			e.add_field(name='Top Commands Today', value=create_list(commands_today))

		e.description = f'{total_uses} total commands issued.'
		e.set_footer(text='Tracking commands since 2018/11/21')

		await ctx.send(embed=e)


def setup(bot):
	bot.add_cog(Meta(bot))
