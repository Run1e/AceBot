import discord, asyncio
from discord.ext import commands
from discord.ext.commands.bot import _default_help_command

from utils.pager import Pager, REQUIRED_PERMS
from cogs.base import TogglableCogMixin

from types import MethodType

IGNORE_COGS = ('Verify', 'Roles', 'Help')


def get_new_ending_note(self):
	command_name = self.context.invoked_with
	ret = (
		'Type {0}{1} command for more info on a command.\n'
		'You can also type {0}{1} category for more info on a category.'.format(self.clean_prefix, command_name)
	)

	if not self.context.bot.pm_help:
		ret += (
			'\n\nFully featured help command might not have run because the bot is missing any of these permissions: '
			+ ', '.join(temp.replace('_', ' ').title() for temp in REQUIRED_PERMS)
		)

	return ret


# rip is just the signature command ripped from the lib, but with alias support removed.
def get_signature(command):
	"""Returns a POSIX-like signature useful for help command output."""
	result = []
	parent = command.full_parent_name

	name = command.name if not parent else parent + ' ' + command.name
	result.append(name)

	if command.usage:
		result.append(command.usage)
		return ' '.join(result)

	params = command.clean_params
	if not params:
		return ' '.join(result)

	for name, param in params.items():
		if param.default is not param.empty:
			# We don't want None or '' to trigger the [name=value] case and instead it should
			# do [name] since [name=None] or [name=] are not exactly useful for the user.
			should_print = param.default if isinstance(param.default, str) else param.default is not None
			if should_print:
				result.append('[%s=%s]' % (name, param.default))
			else:
				result.append('[%s]' % name)
		elif param.kind == param.VAR_POSITIONAL:
			result.append('[%s...]' % name)
		else:
			result.append('<%s>' % name)

	return ' '.join(result)


class HelpPager(Pager):
	commands_per_page = 9

	async def craft_page(self, e, page, entries):
		cog_name, cog_desc, commands = entries[0]

		name = f'{cog_name} Commands'

		if cog_name.lower() in self.bot._toggleable:
			if await self.bot.uses_module(self.guild.id, cog_name.lower()):
				name += ' (enabled)'
			else:
				name += ' (disabled)'

		e.set_author(name=name, icon_url=self.bot.user.avatar_url)
		e.description = cog_desc

		for name, value in commands:
			e.add_field(name=name, value=value, inline=False)

	@classmethod
	def from_bot(cls, ctx):
		self = cls(ctx, [], per_page=1)

		bot = self.bot
		cogs = list(filter(lambda cog: cog.__class__.__name__ not in IGNORE_COGS, bot.cogs.values()))

		# loop cogs
		for index, cog in enumerate(cogs):
			cog_name = cog.__class__.__name__
			cog_desc = cog.__doc__

			cmds = []

			for command_or_group in sorted(bot.get_cog_commands(cog_name), key=lambda cmd: cmd.name):
				if command_or_group.hidden:
					continue

				self.add_command(cmds, command_or_group)

				if isinstance(command_or_group, commands.Group):
					for command in sorted(command_or_group.commands, key=lambda cmd: cmd.name):
						self.add_command(cmds, command)

			self.add_page(cog_name, cog_desc, cmds)

		return self

	@classmethod
	def from_command(cls, ctx, command):
		self = cls(ctx, [], per_page=1)

		cog_name = command.cog_name
		cog_desc = ctx.bot.cogs[cog_name].__doc__

		cmds = []

		self.add_command(cmds, command, brief=False)

		if isinstance(command, commands.Group):
			for cmd in sorted(command.commands, key=lambda cmd: cmd.name):
				self.add_command(cmds, cmd, brief=False)

		self.add_page(cog_name, cog_desc, cmds)

		return self

	@classmethod
	def from_cog(cls, ctx, cog):
		self = cls(ctx, [], per_page=1)

		cmds = []

		cog_name = cog.__class__.__name__

		for cmd in sorted(self.bot.get_cog_commands(cog_name), key=lambda cd: cd.name):
			self.add_command(cmds, cmd, brief=False)

			if isinstance(cmd, commands.Group):
				for group_cmd in sorted(cmd.commands, key=lambda cd: cd.name):
					self.add_command(cmds, group_cmd, brief=False)

		self.add_page(cog_name, cog.__doc__, cmds)

		return self

	def add_page(self, cog_name, cog_desc, cmds):
		'''Will split into several pages to accomodate the per_page limit.'''

		for cmnds in [cmds[i:i + self.commands_per_page] for i in range(0, len(cmds), self.commands_per_page)]:
			self.entries.append((cog_name, cog_desc, cmnds))

	def add_command(self, cmds, command, brief=True):
		if not command.hidden:

			hlp = command.brief or command.help

			if hlp is None:
				hlp = 'No description written.'
			else:
				hlp = hlp.split('\n')[0] if brief else hlp

			if not command.hidden:
				cmds.append((get_signature(command), hlp))

	async def help_embed(self, e):
		e.set_author(name='How do I use the bot?', icon_url=self.bot.user.avatar_url)

		e.description = (
			'Invoke a command by sending the prefix followed by a command name.\n\n'
			'For example, the command signature `define <query>` can be invoked by doing `.define cake`\n\n'
			'The different argument brackets mean:'
		)

		e.add_field(name='<argument>', value='the argument is required.', inline=False)
		e.add_field(name='[argument]', value='the argument is optional.\n\u200b', inline=False)

		e.add_field(name='Support Server', value='Join the support server!\n' + self.bot._support_link)


class Help:
	def __init__(self, bot):
		self.bot = bot
		self.bot.formatter.get_ending_note = MethodType(get_new_ending_note, self.bot.formatter)

	@commands.command(hidden=True, aliases=['oldhelp'])
	async def simplehelp(self, ctx, *commands: str):
		'''Oldschool/default help command.'''

		self.bot.pm_help = not ctx.channel.permissions_for(ctx.guild.me).send_messages

		if not len(commands):
			await _default_help_command(ctx)
		else:
			await _default_help_command(ctx, *commands)

	@commands.command(hidden=True)
	async def help(self, ctx, *, command: str = None):
		'''Help command.'''

		# run default help command if we don't have perms to run interactive one
		perms = ctx.channel.permissions_for(ctx.guild.me)
		if not all(getattr(perms, perm) for perm in REQUIRED_PERMS):
			self.bot.pm_help = not perms.send_messages

			try:
				if command is None:
					await _default_help_command(ctx)
				else:
					await _default_help_command(ctx, command)
			except Exception:
				pass

			return

		if command is None: # all commands if none specified
			p = HelpPager.from_bot(ctx)
		else:

			command = command.lower()
			cog = None

			# search for matching cog
			for cog_name, current_cog in ctx.bot.cogs.items():
				if cog_name.lower() == command and cog_name not in IGNORE_COGS:
					p = HelpPager.from_cog(ctx, current_cog)
					break
			else: # if we didn't find one, try to find a matching command
				command = ctx.bot.get_command(command)
				if command is None: # throw error message if we didn't find a command either
					raise commands.CommandError('Couldn\'t find command/cog.')
				p = HelpPager.from_command(ctx, command)

		await p.go()


def setup(bot):
	bot.add_cog(Help(bot))
