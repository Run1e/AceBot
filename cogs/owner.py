import discord
import io
import textwrap
import traceback
import asyncio
import ast


from discord.ext import commands
from contextlib import redirect_stdout
from tabulate import tabulate
from asyncpg.exceptions import UniqueViolationError
from datetime import datetime

from utils.google import google_parse
from utils.pager import Pager
from utils.time import pretty_datetime
from utils.string_helpers import shorten
from cogs.mixins import AceMixin


class DiscordObjectPager(Pager):
	async def craft_page(self, e, page, entries):
		entry = entries[0]

		e.description = ''

		for field in dir(entry):
			if field.startswith('_'):
				continue

			try:
				attr = getattr(entry, field)
			except AttributeError:
				continue

			if callable(attr):
				continue

			if isinstance(attr, int):
				e.add_field(name=field, value='`{}`'.format(str(attr)), inline=False)

			elif isinstance(attr, str):
				e.add_field(name=field, value=attr, inline=False)

			elif isinstance(attr, datetime):
				e.add_field(name=field, value=pretty_datetime(attr), inline=False)

			elif isinstance(attr, list) and len(attr) and field not in ('members',):
				lst = list()
				for item in attr:
					if hasattr(item, 'mention'):
						lst.append(item.mention)
					elif hasattr(item, 'name'):
						lst.append(item.name)
					elif hasattr(item, 'id'):
						lst.append(item.id)

				if len(lst):
					e.add_field(name=field, value=shorten(' '.join(lst), 1024), inline=False)

		if hasattr(entry, 'name'):
			e.title = entry.name

		if hasattr(entry, 'mention'):
			e.description = entry.mention

		if hasattr(entry, 'avatar_url'):
			e.set_thumbnail(url=entry.avatar_url)
		elif hasattr(entry, 'icon_url'):
			e.set_thumbnail(url=entry.icon_url)


class Owner(AceMixin, commands.Cog):
	'''Commands accessible only to the bot owner.'''

	async def cog_check(self, ctx):
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
			result = await self.db.fetch(query)
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

		if user.bot:
			await ctx.send('Bots cannot be ignored.')
			return

		try:
			await self.db.execute('INSERT INTO ignore (user_id) VALUES ($1)', user.id)
			await ctx.send('User ignored.')
		except UniqueViolationError:
			await ctx.send('User already ignored.')


	@commands.command()
	async def notice(self, ctx, user: discord.User):
		'''Make bot notice an ignored user.'''

		if user.bot:
			await ctx.send('Bots cannot be ignored.')
			return

		res = await self.db.execute('DELETE FROM ignore WHERE user_id=$1', user.id)

		if res == 'DELETE 1':
			await ctx.send('User noticed.')
		else:
			await ctx.send('User not previously ignored.')

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
	async def get(self, ctx, *, query: commands.clean_content):
		'''Get a discord object by specifying key and value.'''

		try:
			tree = ast.parse(query)
		except SyntaxError as exc:
			raise commands.CommandError('Syntax error:\n```{}```'.format(str(exc)))

		def get_objects(lst, iden=None, **kwargs):
			if iden is None and not kwargs:
				return lst
			new_list = []
			for item in lst:
				if iden is not None:
					if isinstance(iden, int):
						if getattr(item, 'id', None) != iden:
							continue
					elif isinstance(iden, str):
						if getattr(item, 'name', None) != iden:
							continue
					else:
						continue
				for key, val in kwargs.items():
					if not getattr(item, key, None) == val:
						continue
				new_list.append(item)
			return new_list

		def guilds(*args, **kwargs):
			return get_objects(ctx.bot.guilds, *args, **kwargs)

		def members(*args, **kwargs):
			return get_objects(ctx.guild.members, *args, **kwargs)

		def roles(*args, **kwargs):
			return get_objects(list(reversed(ctx.guild.roles[1:])), *args, **kwargs)

		def channels(*args, **kwargs):
			return get_objects(ctx.guild.channels, *args, **kwargs)

		def emojis(*args, **kwargs):
			return get_objects(ctx.guild.emojis, *args, **kwargs)

		def categories(*args, **kwargs):
			return get_objects(ctx.guild.categories, *args, **kwargs)

		namespace = dict(
			guilds=guilds,
			members=members,
			roles=roles,
			channels=channels,
			emojis=emojis,
			categories=categories
		)

		def iter_fields(node):
			for field in node._fields:
				try:
					yield field, getattr(node, field)
				except AttributeError:
					pass

		def get_namespace(name):
			if name in namespace:
				return namespace[name]
			else:
				return name

		def do_slice(value, lower, upper, step):
			if callable(lower):
				lower = lower.__name__
			elif not isinstance(lower, str):
				raise SyntaxError('Should be string')

			new_list = list()
			for item in value:
				for subitem in getattr(item, lower, list()):
					if getattr(subitem, upper) == step:
						new_list.append(item)
						break

			return new_list

		def traverse(node):

			def get_value(thing):
				if isinstance(thing, (str, int)):
					return thing

				elif isinstance(thing, ast.Str):
					return thing.s

				elif isinstance(thing, ast.Num):
					return thing.n

				elif isinstance(thing, ast.Name):
					return get_namespace(thing.id)

				else:
					return None

			nval = get_value(node)
			if nval is not None:
				return nval

			for field, value in iter_fields(node):
				if isinstance(value, list):
					for item in value:
						return traverse(item)
				elif isinstance(value, ast.Call):
					func = traverse(value)
					args = [traverse(val) for val in value.args]
					kwargs = {kw.arg: traverse(kw.value) for kw in value.keywords}
					if not callable(func):
						raise SyntaxError('Not callable: \'{}\''.format(str(func)))
					return func(*args, **kwargs)
				elif isinstance(value, ast.Subscript):
					return do_slice(
						traverse(value),
						get_value(value.slice.lower),
						get_value(value.slice.upper),
						get_value(value.slice.step)
					)
				else:
					vval = get_value(value)
					if vval is not None:
						return vval
					else:
						raise SyntaxError('Unsure what to do with: \'{}\ of type \'{}\''.format(
							str(value), str(type(value))
						))

		# print(ast.dump(tree))

		try:
			objects = traverse(tree)
		except SyntaxError as exc:
			raise commands.CommandError('Error when traversing:\n\n{}'.format(str(exc)))

		if not isinstance(objects, list) or not len(objects):
			raise commands.CommandError('No matches found.')

		p = DiscordObjectPager(ctx, entries=objects, per_page=1)
		await p.go()

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
			'db': self.db
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
