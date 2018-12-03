import discord, io, textwrap, traceback
from discord.ext import commands
from contextlib import redirect_stdout

from utils.database import IgnoredUser, UniqueViolationError

OK_EMOJI = '\U00002705'
NOTOK_EMOJI = '\U0000274C'
ERROR_EMOJI = '\U0001F1E9'
DUPE_EMOJI = '\U0001F1E9'
NOTFOUND_EMOJI = '\U0001F1F3'


class Owner:
	'''Owner commands.'''
	
	def __init__(self, bot):
		self.bot = bot
	
	async def __local_check(self, ctx):
		return await self.bot.is_owner(ctx.author)
	
	def cleanup_code(self, content):
		'''Automatically removes code blocks from the code.'''
		# remove ```py\n```
		if content.startswith('```') and content.endswith('```'):
			return '\n'.join(content.split('\n')[1:-1])
		
		# remove `foo`
		return content.strip('` \n')
	
	@commands.command(name='reload', aliases=['rl'], hidden=True)
	async def _reload(self, ctx, *, module: str):
		'''Reloads a module.'''
		
		try:
			module = 'cogs.' + module
			self.bot.unload_extension(module)
			self.bot.load_extension(module)
		except Exception:
			await ctx.send(f'```py\n{traceback.format_exc()}\n```')
		else:
			await ctx.message.add_reaction('\N{OK HAND SIGN}')
	
	@commands.command(hidden=True)
	async def ignore(self, ctx, user: discord.User):
		'''Make bot ignore a user.'''
		
		try:
			await IgnoredUser.create(user_id=user.id)
		except UniqueViolationError:
			emoji = DUPE_EMOJI
		except:
			emoji = NOTOK_EMOJI
		else:
			emoji = OK_EMOJI
		
		await ctx.message.add_reaction(emoji)
	
	@commands.command(hidden=True)
	async def notice(self, ctx, user: discord.User):
		'''Make bot notice an ignore user.'''
		
		user = await IgnoredUser.get(user.id)
		
		if user is None:
			emoji = NOTFOUND_EMOJI
		else:
			if await user.delete() != 'DELETE 1':
				emoji = NOTOK_EMOJI
			else:
				emoji = OK_EMOJI
		
		await ctx.message.add_reaction(emoji)
	
	@commands.command(hidden=True)
	async def eval(self, ctx, *, body: str):
		'''Evaluates some code.'''
		
		env = {
			'discord': discord,
			'bot': self.bot,
			'ctx': ctx,
			'channel': ctx.channel,
			'author': ctx.author,
			'guild': ctx.guild,
			'message': ctx.message
		}
		
		env.update(globals())
		
		body = self.cleanup_code(body)
		stdout = io.StringIO()
		
		to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'
		
		try:
			exec(to_compile, env)
		except Exception as e:
			return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')
		
		func = env['func']
		try:
			with redirect_stdout(stdout):
				ret = await func()
		except Exception as e:
			value = stdout.getvalue()
			await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
		else:
			value = stdout.getvalue()
			try:
				await ctx.message.add_reaction('\u2705')
			except:
				pass
			
			if ret is None:
				if value:
					await ctx.send(f'```py\n{value}\n```')
			else:
				await ctx.send(f'```py\n{value}{ret}\n```')


def setup(bot):
	bot.add_cog(Owner(bot))
