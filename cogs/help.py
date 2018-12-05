import discord, asyncio
from discord.ext import commands

from cogs.base import TogglableCogMixin

NEXT_EMOJI = '⏩'
PREV_EMOJI = '⏪'
STOP_EMOJI = '⏹'
FIRST_EMOJI = '⏮'
LAST_EMOJI = '⏭'
HELP_EMOJI = '❔'


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


class EmbedHelp:
	ignore_cogs = ('Verify', 'Roles', 'Help')
	
	pages = []
	cogs = []
	commands = {}
	help_page = None
	
	def __init__(self, ctx):
		self.ctx = ctx
		self.index = 0
	
	@classmethod
	def _make_embeds(cls, bot):
		cogs = list(filter(lambda cog: cog.__class__.__name__ not in cls.ignore_cogs, bot.cogs.values()))
		for index, cog in enumerate(cogs):
			
			cog_name = cog.__class__.__name__
			
			e = discord.Embed(
				description=cog.__doc__
			)
			
			e.set_footer(text=f'Page {index + 1}/{len(cogs)}')
			
			def add_command(command):
				e.add_field(
					name=get_signature(command),
					value=command.brief or command.help,
					inline=False
				)
				
				cls.commands[command.qualified_name] = index
				for alias in command.aliases:
					cls.commands[alias] = index
			
			for command_or_group in sorted(bot.get_cog_commands(cog_name), key=lambda cmd: cmd.name):
				if command_or_group.hidden:
					continue
				
				if isinstance(command_or_group, commands.Group):
					cls.commands[command_or_group.name] = index
					for command in sorted(command_or_group.commands, key=lambda cmd: cmd.name):
						add_command(command)
				else:
					add_command(command_or_group)
			
			e.add_field(name='Support Server', value=bot._support_link)
			
			e.set_author(name=f'{cog_name} Commands', icon_url=bot.user.avatar_url)
			
			cls.cogs.append(cog)
			cls.pages.append(e)
		
		# help page
		
		e = discord.Embed(
			title='How do I use the bot?',
			description='Invoke a command by sending the prefix followed by a command name.\n\nFor example, the command'
						' signature `define <query>` can be invoked by doing `.define bot`\n\nThe different argument'
						' brackets mean:'
		)
		
		e.add_field(name='<argument>', value='means the argument is required.', inline=False)
		e.add_field(name='[argument]', value='means the argument is optional.', inline=False)
		
		cls.help_page = e
	
	def help(self):
		return self.help_page
	
	def next(self):
		if len(self.pages) - 1 != self.index:
			self.index += 1
	
	def prev(self):
		if self.index != 0:
			self.index -= 1
	
	def first(self):
		self.index = 0
	
	def last(self):
		self.index = len(self.pages) - 1


class Help:
	emojis = (FIRST_EMOJI, PREV_EMOJI, NEXT_EMOJI, LAST_EMOJI, STOP_EMOJI, HELP_EMOJI)
	
	def __init__(self, bot):
		self.bot = bot
		EmbedHelp._make_embeds(bot)
	
	@commands.command(hidden=True)
	@commands.bot_has_permissions(add_reactions=True)
	async def help(self, ctx, *, command: str = None):
		eh = EmbedHelp(ctx)
		
		if command is not None:
			command = command.lower()
			
			if command in eh.commands:
				eh.index = eh.commands[command]
			else:
				for index, cog in enumerate(eh.cogs):
					if command == cog.__class__.__name__.lower():
						eh.index = index
						break
		
		embed = eh.pages[eh.index]
		msg = await ctx.send(embed=embed)
		
		def pred(reaction, user):
			return reaction.message.id == msg.id and user != self.bot.user
		
		for emoji in self.emojis:
			await msg.add_reaction(emoji)
		
		while True:
			try:
				reaction, user = await self.bot.wait_for('reaction_add', check=pred, timeout=60.0)
			except asyncio.TimeoutError:
				await msg.clear_reactions()
				return
			else:
				if reaction.emoji == STOP_EMOJI:
					await msg.clear_reactions()
					return
				
				if reaction.emoji == NEXT_EMOJI:
					eh.next()
				elif reaction.emoji == PREV_EMOJI:
					eh.prev()
				elif reaction.emoji == FIRST_EMOJI:
					eh.first()
				elif reaction.emoji == LAST_EMOJI:
					eh.last()
				elif reaction.emoji == HELP_EMOJI:
					await msg.edit(embed=eh.help())
					await msg.remove_reaction(reaction.emoji, user)
					continue
				else:
					await msg.remove_reaction(reaction.emoji, user)
					continue
				
				cog = eh.cogs[eh.index]
				e = eh.pages[eh.index]
				
				if isinstance(cog, TogglableCogMixin):
					state = await ctx.bot.uses_module(ctx, cog.__class__.__name__)
					
					# this is honestly quite the hack and I don't like it but I think it's okay
					# also it shouldn't really be here z
					e_dict = e.to_dict()
					e = discord.Embed(**e_dict)
					for field in e_dict['fields']:
						e.add_field(**field)
					e.set_footer(**e_dict['footer'])
					e.set_author(
						name=e_dict['author']['name'] + f" ({'enabled' if state else 'disabled'})",
						icon_url=e_dict['author']['icon_url']
					)
				
				await msg.edit(embed=e)
				await msg.remove_reaction(reaction.emoji, user)


def setup(bot):
	bot.add_cog(Help(bot))
