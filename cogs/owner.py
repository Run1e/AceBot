import io
import textwrap
import traceback
from contextlib import redirect_stdout

import discord
from discord.ext import commands

from utils.database import IgnoredUser, UniqueViolationError


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
	
	@commands.command(name='reload', aliases=['re'], hidden=True)
	async def _reload(self, ctx, *, module):
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
			emoji = '\U0001F1E9'
		except:
			emoji = '\U0000274C'
		else:
			emoji = '\U00002705'
			
		await ctx.message.add_reaction(emoji)
		
	@commands.command(hidden=True)
	async def notice(self, ctx, user: discord.User):
		'''Make bot notice an ignore user.'''
		
		user = await IgnoredUser.get(user.id)
		
		if user is None:
			emoji = '\U0001F1F3'
		else:
			if await user.delete() != 'DELETE 1':
				emoji = '\U0000274C'
			else:
				emoji = '\U00002705'
		
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
