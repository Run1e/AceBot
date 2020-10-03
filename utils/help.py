from discord.ext import commands

from utils.pager import Pager


class HelpPager(Pager):
	commands_per_page = 8

	def add_page(self, cog_name, cog_desc, commands):
		'''Will split into several pages to accommodate the per_page limit.'''

		# will obviously not run if no commands are in the page
		for commands_slice in [commands[i:i + self.commands_per_page] for i in range(0, len(commands), self.commands_per_page)]:
			self.entries.append((cog_name, cog_desc, commands_slice))

	def craft_invite_string(self):
		return '[Enjoying the bot? Invite it to your own server!]({0})'.format(self.ctx.bot.invite_link)

	async def craft_page(self, e, page, entries):
		cog_name, cog_desc, commands = entries[0]

		name = f'{cog_name} Commands'

		desc = ''
		if self.ctx.guild.owner != self.ctx.author:
			desc += self.craft_invite_string()

		if cog_desc is not None:
			desc += '\n\n' + cog_desc

		self.embed.set_author(name=name, icon_url=self.bot.user.avatar_url)
		self.embed.description = desc

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

	async def package_command(self, command, force=False, long_help=False):
		if command.hidden:
			return None

		if not force:
			try:
				if not await command.can_run(self.context):
					return None
			except commands.CommandError:
				return None

		help_message = command.brief or command.help

		if help_message is None:
			help_message = 'No description available.'
		elif not long_help:
			help_message = help_message.split('\n')[0]

		# unsure if I want this
		#if command.aliases:
		#	help_message += '\nAliases: `' + ', '.join(command.aliases) + '`'

		return self.context.prefix + get_signature(command), help_message

	async def prepare_help_command(self, ctx, command=None):
		self.context = ctx
		self.pager = HelpPager(ctx, list(), per_page=1)

	async def add_cog(self, cog, force=False):
		cog_name = cog.__class__.__name__
		cog_desc = cog.__doc__

		commands = []
		added = []

		for command in cog.walk_commands():
			if command in added:
				continue

			added.append(command)

			pack = await self.package_command(command, force=force)
			if pack is None:
				continue

			commands.append(pack)

		if not commands:
			return True

		self.pager.add_page(cog_name, cog_desc, commands)

	async def send_bot_help(self, mapping):
		for cog in mapping:
			if cog is not None:
				await self.add_cog(cog)

		await self.pager.go()

	async def send_cog_help(self, cog):
		if await self.add_cog(cog, force=True):
			return
		await self.pager.go()

	async def send_group_help(self, group):
		cog_name = group.cog_name

		if cog_name is not None and group.cog_name.lower() == group.name.lower():
			await self.send_cog_help(group.cog)
			return

		commands = []
		seen = []

		for command in group.walk_commands():
			if command in seen:
				continue

			seen.append(command)

			pack = await self.package_command(command)
			if pack is None:
				continue

			commands.append(pack)

		# if we found no commands, just stop here
		if not commands:
			await self.stop()
			return

		self.pager.add_page(group.cog_name, group.cog.__doc__, commands)
		await self.pager.go()

	async def send_command_help(self, command):
		cog_name = command.cog_name

		if cog_name is not None and cog_name.lower() == command.name:
			await self.send_cog_help(command.cog)
			return

		pack = await self.package_command(command, force=True, long_help=True)

		if pack is None:  # probably means it's hidden
			await self.stop()
			return

		self.pager.add_page(cog_name, command.cog.__doc__, [pack])
		await self.pager.go()

	async def stop(self):
		await self.send_error_message(await self.command_not_found(self.context.kwargs['command']))

	async def command_not_found(self, command_name):
		return commands.CommandNotFound(command_name)

	async def send_error_message(self, error):
		if not isinstance(error, commands.CommandNotFound):
			return

		command_name = str(error)

		for cog in self.context.bot.cogs:
			if command_name == cog.lower():
				await self.send_cog_help(self.context.bot.get_cog(cog))
				return

		await self.context.send('Command \'{0}\' not found.'.format(command_name))


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
