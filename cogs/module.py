import discord
from discord.ext import commands

from utils.database import GuildModule
from sqlalchemy import and_

class Modules:
	'''Manage modules.'''
	
	def __init__(self, bot):
		self.bot = bot
	
	async def __local_check(self, ctx):
		return ctx.guild.owner is ctx.author or await self.bot.is_owner(ctx.author)
	
	@commands.group()
	async def mod(self, ctx):
		'''Manage bot modules.'''
		
		if ctx.invoked_subcommand is not None:
			return
		
		help_text = await self.bot.formatter.format_help_for(ctx, ctx.command)
		await ctx.send('\n'.join(help_text[0].split('\n')[:-3]) + '```')
		
	@mod.command()
	async def list(self, ctx):
		'''List modules.'''
		
		mods = await GuildModule.query.where(
			GuildModule.guild_id == ctx.guild.id
		).gino.all()
		
		mod_list = []
		
		for modu in mods:
			mod_list.append(modu.module)
			
		e = discord.Embed(title='Modules', description='See `.help mod` for more commands.')
		
		enabled = '\n'.join(mod_list)
		disabled = '\n'.join([mod for mod in self.bot._toggleable if mod not in mod_list])
		
		e.add_field(name='Enabled', value=enabled if len(enabled) else 'None')
		e.add_field(name='Disabled', value=disabled if len(disabled) else 'None')
		
		await ctx.send(embed=e)
	
	@mod.command()
	async def info(self, ctx, module: str):
		'''Show info about a module.'''
		
		lower = module.lower()
		if lower not in self.bot._toggleable:
			raise commands.CommandError(f'{lower} is not a toggleable module.')
		
		for cog in self.bot.cogs:
			if lower == cog.lower():
				module = cog
				break
				
		cog = self.bot.get_cog(module)
		cog_commands = self.bot.get_cog_commands(module)
		
		cmds = []
		cmds_brief = []
		
		for command in cog_commands:
			cmds.append(command.name)
			cmds_brief.append('-' if command.help is None else command.help)
			
		e = discord.Embed(title=cog.__class__.__name__, description=cog.__doc__)
		
		if len(cmds):
			e.add_field(name='Command', value='\n'.join(cmds))
			e.add_field(name='Description', value='\n'.join(cmds_brief))
		
		await ctx.send(embed=e)
	
	@mod.command()
	async def enable(self, ctx, module: str):
		'''Enable a module.'''
		
		module = module.lower()
		if module not in self.bot._toggleable:
			raise commands.CommandError(f'Module `{module}` is not a valid module.')
		
		if await self.bot.uses_module(ctx, module):
			return await ctx.send(f'Module `{module}` already enabled.')
		
		result = await GuildModule.create(
			guild_id=ctx.guild.id,
			module=module
		)
		
		if result is None:
			raise commands.CommandError(f'Failed enabling module `{module}`')
		
		await ctx.send(f'Module `{module}` successfully enabled.')
			
	@mod.command()
	async def disable(self, ctx, module: str):
		'''Disable a module.'''
	
		module = module.lower()
		if module not in self.bot._toggleable:
			raise commands.CommandError(f'{module} is not a valid module.')
		
		mod = await GuildModule.query.where(
			and_(
				GuildModule.guild_id == ctx.guild.id,
				GuildModule.module == module
			)
		).gino.first()
		
		if mod is None:
			return await ctx.send(f'Module `{module}` is not currently enabled.')
		
		if await mod.delete() == 'DELETE 1':
			await ctx.send(f'Module `{module}` disabled.')
		else:
			raise commands.CommandError(f'Failed disabling module `{module}`')

def setup(bot):
	bot.add_cog(Modules(bot))
