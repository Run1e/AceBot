import discord, io, textwrap, traceback, asyncio
from discord.ext import commands
from contextlib import redirect_stdout
from tabulate import tabulate

from utils.database import db, IgnoredUser, UniqueViolationError
from utils.google import google_parse

OK_EMOJI = '\N{HEAVY CHECK MARK}'
NOTOK_EMOJI = '\N{CROSS MARK}'
DUPE_EMOJI = '\N{REGIONAL INDICATOR SYMBOL LETTER D}'


class Owner:
	'''Commands accessible only to the bot owner.'''

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

	@commands.command()
	async def sql(self, ctx, *, query: str):
		'''Execute a SQL query.'''

		try:
			result = await db.all(query)
		except Exception as exc:
			raise commands.CommandError(str(exc))

		if not len(result):
			await ctx.send('No rows returned.')
			return

		table = tabulate(result, result[0].keys())

		if len(table) > 1994:
			fp = io.BytesIO(table.encode('utf-8'))
			await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
		else:
			await ctx.send('```' + table + '```')

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
	async def gh(self, ctx, *, query: str):
		'''Google search for GitHub pages.'''

		await ctx.invoke(self.google, query='site:github.com ' + query)

	@commands.command(hidden=True)
	async def f(self, ctx, *, query: str):
		'''Google search for AutoHotkey pages.'''

		await ctx.invoke(self.google, query='site:autohotkey.com ' + query)

	@commands.command(aliases=['g'])
	@commands.bot_has_permissions(embed_links=True)
	async def google(self, ctx, *, query: str):
		'''Get first result from google.'''

		headers = {
			'User-Agent': (
				'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) '
				'Chrome/39.0.2171.95 Safari/537.36'
			),
			'Accept:': 'text/html'
		}

		async with ctx.channel.typing():
			try:
				async with self.bot.aiohttp.get(f'http://google.com/search', params=dict(hl='en', safe='on', q=query),
												headers=headers) as resp:
					if resp.status != 200:
						raise commands.CommandError(f'Query returned status {resp.status} {resp.reason}')
					result = google_parse(await resp.text())
					if not result:
						raise commands.CommandError('No results.')
					else:
						embed = discord.Embed(title=result[0], url=result[1], description=result[2])
						embed.set_footer(text=result[3])
						# embed.set_image(url=f'https://{result[3]}/favicon.ico')
						await ctx.send(embed=embed)

			except asyncio.TimeoutError:
				raise commands.CommandError('Query timed out.')

	@commands.command()
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

	@commands.command()
	async def notice(self, ctx, user: discord.User):
		'''Make bot notice an ignored user.'''

		user = await IgnoredUser.get(user.id)

		if await user.delete() != 'DELETE 1':
			emoji = NOTOK_EMOJI
		else:
			emoji = OK_EMOJI

		await ctx.message.add_reaction(emoji)

	@commands.command(hidden=True)
	async def pm(self, ctx, user: discord.User, *, content: str):
		'''Private message a user.'''
		await user.send(content)

	@commands.command(hidden=True)
	async def say(self, ctx, channel: discord.TextChannel, *, content: str):
		'''Send a message in a channel.'''

		await ctx.message.delete()
		await channel.send(content)

	@commands.command(hidden=True)
	async def print(self, ctx, *, body: str):
		'''Calls eval but wraps code in print()'''

		await ctx.invoke(self.eval, body=f'pprint({body})')

	@commands.command()
	async def eval(self, ctx, *, body: str):
		'''Evaluates some code.'''

		from pprint import pprint
		from tabulate import tabulate

		env = {
			'discord': discord,
			'bot': self.bot,
			'ctx': ctx,
			'channel': ctx.channel,
			'author': ctx.author,
			'guild': ctx.guild,
			'message': ctx.message,
			'pprint': pprint,
			'tabulate': tabulate,
			'db': db
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
					if len(value) > 1994:
						fp = io.BytesIO(value.encode('utf-8'))
						await ctx.send('Log too large...', file=discord.File(fp, 'results.txt'))
					else:
						await ctx.send(f'```py\n{value}\n```')


def setup(bot):
	bot.add_cog(Owner(bot))
