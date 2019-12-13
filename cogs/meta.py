import discord
import inspect

from discord.ext import commands
from datetime import datetime, timedelta

from cogs.mixins import AceMixin
from utils.time import pretty_timedelta
from utils.string_helpers import repr_ctx

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
	@commands.bot_has_permissions(embed_links=True)
	async def stats(self, ctx, member: discord.Member = None):
		'''Show bot or user command stats.'''

		if member is None:
			await self._stats_guild(ctx)
		else:
			await self._stats_member(ctx, member)

	async def _stats_member(self, ctx, member):
		past_day = datetime.utcnow() - timedelta(days=1)

		first_command = await self.db.fetchval(
			'SELECT timestamp FROM log WHERE guild_id=$1 AND user_id=$2 LIMIT 1',
			ctx.guild.id, member.id
		)

		total_uses = await self.db.fetchval(
			'SELECT COUNT(id) FROM log WHERE guild_id=$1 AND user_id=$2',
			ctx.guild.id, member.id
		)

		commands_alltime = await self.db.fetch(
			'SELECT COUNT(id), command FROM log WHERE guild_id=$1 AND user_id=$2 GROUP BY command '
			'ORDER BY COUNT DESC LIMIT 5', ctx.guild.id, member.id
		)

		commands_today = await self.db.fetch(
			'SELECT COUNT(id), command FROM log WHERE guild_id=$1 AND user_id=$2 AND timestamp > $3 '
			'GROUP BY command ORDER BY COUNT DESC LIMIT 5', ctx.guild.id, member.id, past_day
		)

		e = discord.Embed()
		e.set_author(name=member.name, icon_url=member.avatar_url)
		e.add_field(name='Top Commands', value=self._stats_craft_list(commands_alltime))
		e.add_field(name='Top Commands Today', value=self._stats_craft_list(commands_today))

		self._stats_embed_fill(e, total_uses, first_command)

		await ctx.send(embed=e)

	async def _stats_guild(self, ctx):
		past_day = datetime.utcnow() - timedelta(days=1)
		total_uses = await self.db.fetchval('SELECT COUNT(id) FROM log WHERE guild_id=$1', ctx.guild.id)

		first_command = await self.db.fetchval(
			'SELECT timestamp FROM log WHERE guild_id=$1 LIMIT 1', ctx.guild.id
		)

		commands_today = await self.db.fetch(
			'SELECT COUNT(id), command FROM log WHERE guild_id=$1 AND timestamp > $2 GROUP BY command '
			'ORDER BY COUNT DESC LIMIT 5', ctx.guild.id, past_day
		)

		commands_alltime = await self.db.fetch(
			'SELECT COUNT(id), command FROM log WHERE guild_id=$1 GROUP BY command ORDER BY COUNT DESC LIMIT 5',
			ctx.guild.id
		)

		users_today = await self.db.fetch(
			'SELECT COUNT(id), user_id FROM log WHERE guild_id=$1 AND timestamp > $2 GROUP BY user_id '
			'ORDER BY COUNT DESC LIMIT 5', ctx.guild.id, past_day
		)

		users_alltime = await self.db.fetch(
			'SELECT COUNT(id), user_id FROM log WHERE guild_id=$1 GROUP BY user_id '
			'ORDER BY COUNT DESC LIMIT 5', ctx.guild.id
		)

		e = discord.Embed()
		e.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
		e.add_field(name='Top Commands', value=self._stats_craft_list(commands_alltime))
		e.add_field(name='Top Commands Today', value=self._stats_craft_list(commands_today))

		e.add_field(
			name='Top Users',
			value=self._stats_craft_list(users_alltime, [f'<@{user_id}>' for _, user_id in users_alltime])
		)

		e.add_field(
			name='Top Users Today',
			value=self._stats_craft_list(users_today, [f'<@{user_id}>' for _, user_id in users_today])
		)

		self._stats_embed_fill(e, total_uses, first_command)

		await ctx.send(embed=e)

	def _stats_embed_fill(self, e, total_uses, first_command):
		e.description = f'{total_uses} total commands issued.'
		if first_command is not None:
			e.timestamp = first_command
			e.set_footer(text='First command invoked')

	def _stats_craft_list(self, cmds, members=None):
		value = ''
		for index, cmd in enumerate(cmds):
			value += f'\n{MEDALS[index]} {members[index] if members else cmd[1]} ({cmd[0]} uses)'

		if not len(value):
			return 'None so far!'

		return value[1:]

	@commands.command(hidden=True)
	@commands.bot_has_permissions(embed_links=True)
	async def about(self, ctx, command_name: str = None):
		'''See the aliases for a given command.'''

		if command_name is None:
			await self._about_bot(ctx)
		else:
			cmd = self.bot.get_command(command_name)
			if cmd is None:
				raise commands.CommandError('No command with that name found.')
			await self._about_command(ctx, cmd)

	async def _about_bot(self, ctx):
		e = discord.Embed()

		e.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)

		await ctx.send(embed=e)

	async def _about_command(self, ctx, command):
		raise commands.CommandError('Not implemented yet.')

	@commands.command(aliases=['fb'])
	@commands.cooldown(rate=1, per=60.0, type=commands.BucketType.user)
	async def feedback(self, ctx, *, feedback: str):
		'''Give me some feedback about the bot!'''

		timestamp = str(datetime.utcnow()).split('.')[0].replace(' ', '_').replace(':', '')
		filename = str(ctx.message.id) + '_' + timestamp

		content = '{}\n\n{}'.format(repr_ctx(ctx), feedback)

		with open('feedback/{}.feedback'.format(filename), 'w', encoding='utf-8-sig') as f:
			f.write(content)

		await ctx.send('Feedback sent. Thanks for helping improve the bot!')

	@commands.command(aliases=['join'])
	async def invite(self, ctx):
		'''Get bot invite link.'''

		await ctx.send(self.bot.invite_link)

	@commands.command()
	async def support(self, ctx):
		'''Get link to support server.'''

		await ctx.send(self.bot.support_link)

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

		paginator = commands.Paginator(prefix='```py')
		for line in code.replace('`', '\u200b`').split('\n'):
			paginator.add_line(line)

		for page in paginator.pages:
			await ctx.send(page)

	@commands.command()
	async def uptime(self, ctx):
		'''Time since last bot restart.'''

		await ctx.send(
			f'It has been {pretty_timedelta(datetime.utcnow() - self.bot.startup_time)} '
			'since the last bot restart.'
		)

	@commands.command()
	async def dbl(self, ctx):
		'''Get link to discordbots.org bot page.'''

		await ctx.send('https://top.gg/bot/{0.id}'.format(self.bot.user))

	@commands.command(hidden=True)
	async def hello(self, ctx):
		await ctx.send(f'Hello {ctx.author.mention}!')

	@commands.command(hidden=True)
	async def speedtest(self, ctx):
		'''Check response time.'''

		msg = await ctx.send('Wait...')

		await msg.edit(content='Response: {}.\nGateway: {}'.format(
			pretty_timedelta(msg.created_at - ctx.message.created_at),
			pretty_timedelta(timedelta(seconds=self.bot.latency))
		))


def setup(bot):
	bot.add_cog(Meta(bot))
