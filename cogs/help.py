import discord
from discord.ext import commands

from utils.pager import Pager


class HelpPager(Pager):
	commands_per_page = 8

	def add_page(self, cog_name, cog_desc, cmds):
		'''Will split into several pages to accomodate the per_page limit.'''

		# will obviously not run if no commands are in the page
		for cmds_slice in [cmds[i:i + self.commands_per_page] for i in range(0, len(cmds), self.commands_per_page)]:
			self.entries.append((cog_name, cog_desc, cmds_slice))

	async def craft_page(self, e, page, entries):
		cog_name, cog_desc, commands = entries[0]

		name = f'{cog_name} Commands'

		self.embed.set_author(name=name, icon_url=self.bot.user.avatar_url)
		self.embed.description = cog_desc

		for name, value in commands:
			self.embed.add_field(name=name, value=value, inline=False)

	async def help_embed(self, e):
		e.set_author(name='How do I use the bot?', icon_url=self.bot.user.avatar_url)

		e.description = (
			'Invoke a command by sending the prefix followed by a command name.\n\n'
			'For example, the command signature `track <query>` can be invoked by doing `track yellow`\n\n'
			'The different argument brackets mean:'
		)

		e.add_field(name='<argument>', value='the argument is required.', inline=False)
		e.add_field(name='[argument]', value='the argument is optional.\n\u200b', inline=False)

		e.add_field(name='Support Server', value='Join the support server!\n' + self.bot.support_link)


class PaginatedHelpCommand(commands.HelpCommand):
	'''Cog that implements the help command and help pager.'''

	async def add_command(self, cmds, command, force=False):
		if command.hidden:
			return

		if force is False:
			try:
				if not await command.can_run(self.context):
					return
			except commands.CheckFailure:
				return

		help_message = command.brief or command.help

		if help_message is None:
			help_message = 'No description available.'
		else:
			help_message = help_message.split('\n')[0]

		cmds.append((self.context.prefix + get_signature(command), help_message))

	async def prepare_help_command(self, ctx, command=None):
		self.context = ctx
		self.pager = HelpPager(ctx, list(), per_page=1)

	async def add_cog(self, cog):
		cog_name = cog.__class__.__name__
		cog_desc = cog.__doc__

		cmds = []

		added = []
		for command in cog.walk_commands():
			if command in added:
				continue

			await self.add_command(cmds, command)
			added.append(command)

		self.pager.add_page(cog_name, cog_desc, cmds)

	async def send_bot_help(self, mapping):
		for cog in mapping:
			if cog is not None:
				await self.add_cog(cog)

		await self.pager.go()

	async def send_cog_help(self, cog):
		await self.add_cog(cog)
		await self.pager.go()

	async def send_group_help(self, group):
		if group.cog_name.lower() == group.name.lower():
			await self.send_cog_help(group.cog)
			return

		added = []
		cmds = []

		for command in group.walk_commands():
			if command in added:
				continue

			await self.add_command(cmds, command)
			added.append(command)

		self.pager.add_page(group.cog_name, group.cog.__doc__, cmds)
		await self.pager.go()

	async def send_command_help(self, command):
		cog_name = command.cog_name

		if cog_name is not None and cog_name.lower() == command.name:
			await self.send_cog_help(command.cog)
			return

		cog_desc = command.cog.__doc__

		cmds = []

		await self.add_command(cmds, command)
		self.pager.add_page(cog_name, cog_desc, cmds)

		await self.pager.go()

	async def command_not_found(self, string):
		return commands.CommandNotFound(string)

	async def send_error_message(self, error):
		if not isinstance(error, commands.CommandNotFound):
			return

		cmd = str(error)

		for cog in self.context.bot.cogs:
			if cmd == cog.lower():
				await self.send_cog_help(self.context.bot.get_cog(cog))
				return

		await self.context.send('Command \'{}\' not found.'.format(cmd))


class EditedMinimalHelpCommand(commands.MinimalHelpCommand):
	def get_ending_note(self):
		return (
			'The interactive help menu did not get sent because the bot is missing '
			'the following permissions: ' + ', '.join(self.missing_perms)
		)

	async def send_error_message(self, error):
		return


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
