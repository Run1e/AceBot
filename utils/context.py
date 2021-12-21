import disnake
import asyncio

from disnake.ext import commands

from utils.pager import STATIC_PERMS
from utils.time import pretty_datetime
from utils.string import po

PROMPT_REQUIRED_PERMS = ('embed_links', 'add_reactions')
PROMPT_EMOJIS = ('\N{WHITE HEAVY CHECK MARK}', '\N{CROSS MARK}')


async def is_mod_pred(ctx):
	return await ctx.is_mod()


def is_mod():
	return commands.check(is_mod_pred)


async def can_prompt_pred(ctx):
	perms = ctx.perms
	missing_perms = list(perm for perm in PROMPT_REQUIRED_PERMS if not getattr(perms, perm))

	if not missing_perms:
		return True

	raise commands.BotMissingPermissions(missing_perms)


def can_prompt():
	return commands.check(can_prompt_pred)


class AceContext(commands.Context):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)

	@property
	def db(self):
		return self.bot.db

	@property
	def http(self):
		return self.bot.aiohttp

	@property
	def perms(self):
		return self.channel.permissions_for(self.guild.me)

	@property
	def pretty(self):
		return '{0.display_name} ({0.id}) in {1.name} ({1.id})'.format(self.author, self.guild)

	@property
	def stamp(self):
		return 'TIME: {}\nGUILD: {}\nCHANNEL: #{}\nAUTHOR: {}\nMESSAGE ID: {}'.format(
			pretty_datetime(self.message.created_at), po(self.guild), po(self.channel),
			po(self.author), str(self.message.id)
		)

	async def is_mod(self, member=None):
		'''Check if invoker or member has bot moderator rights.'''

		member = member or self.author

		# always allow bot owner
		if member.id == self.bot.owner_id:
			return True

		# true if member has administrator perms in this channel
		if self.channel.permissions_for(member).administrator:
			return True

		# only last way member can be mod if they're in the moderator role
		gc = await self.bot.config.get_entry(member.guild.id)

		# false if not set
		if gc.mod_role_id is None:
			return False

		# if set, see if author has this role

		return bool(disnake.utils.get(member.roles, id=gc.mod_role_id))

	async def send_help(self, command=None):
		'''Convenience method for sending help.'''

		perms = self.perms
		missing_perms = list(perm for perm in STATIC_PERMS if not getattr(perms, perm))

		if missing_perms:
			help_cmd = self.bot.static_help_command
			help_cmd.missing_perms = missing_perms
		else:
			help_cmd = self.bot.help_command

		help_cmd.context = self

		if isinstance(command, commands.Command):
			command = command.qualified_name

		await help_cmd.command_callback(self, command=command)

	async def prompt(self, title=None, prompt=None, user_override=None):
		'''Creates a yes/no prompt.'''

		perms = self.perms
		if not all(getattr(perms, perm) for perm in PROMPT_REQUIRED_PERMS):
			return False

		prompt = prompt or 'No description provided.'
		prompt += '\n\nPress {} to continue, {} to abort.'.format(*PROMPT_EMOJIS)

		e = disnake.Embed(description=prompt)

		e.set_author(name=title or 'Prompt', icon_url=self.bot.user.display_avatar.url)

		try:
			msg = await self.send(content=None if user_override is None else user_override.mention, embed=e)
			for emoji in PROMPT_EMOJIS:
				await msg.add_reaction(emoji)
		except disnake.HTTPException:
			return False

		check_user = user_override or self.author

		def check(reaction, user):
			return reaction.message.id == msg.id and user == check_user and str(reaction) in PROMPT_EMOJIS

		try:
			reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=60.0)
			return str(reaction) == PROMPT_EMOJIS[0]
		except (asyncio.TimeoutError, disnake.HTTPException):
			return False
		finally:
			try:
				await msg.delete()
			except disnake.HTTPException:
				pass

	async def admin_prompt(self, raise_on_abort=True):
		result = await self.prompt(
			title='Warning!',
			prompt=(
				'You are about to do an administrative action on an item you do not own.\n\n'
				'Are you sure you want to continue?'
			)
		)

		if raise_on_abort and not result:
			raise commands.CommandError('Administrative action aborted.')

		return result
