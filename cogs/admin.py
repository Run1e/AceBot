import discord
from discord.ext import commands

import json, io, textwrap, traceback, os
from shutil import copy2
from datetime import datetime
from contextlib import redirect_stdout

from cogs.utils.google_result import google_result

class Admin:
	"""Admin commands"""

	def __init__(self, bot):
		self.bot = bot

	def cleanup_code(self, content):
		"""Automatically removes code blocks from the code."""
		# remove ```py\n```
		if content.startswith('```') and content.endswith('```'):
			return '\n'.join(content.split('\n')[1:-1])

		# remove `foo`
		return content.strip('` \n')

	async def __local_check(self, ctx):
		return await self.bot.is_owner(ctx.author)

	@commands.command()
	async def backup(self, ctx):
		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		directory = f'lib/backups/{timestamp}/'
		try:
			if not os.path.exists(directory):
				os.makedirs(directory)
			copy2('lib/tags.db', directory)
			copy2('lib/reps.db', directory)
		except Exception as ex:
			await ctx.send(f'```{str(ex)}```')
			return
		await ctx.send(f'Databases backed up under `{timestamp}`', delete_after=5)


	# if this doesn't work, I changed how id is casted to int
	@commands.command()
	async def leave(self, ctx, *, id: int):
		"""Leave a guild."""
		for guild in self.bot.guilds:
			if (guild.id == id):
				await guild.leave()
				await ctx.send(f'Left {guild.name}.')

	@commands.command()
	async def say(self, ctx, *, text: str):
		"""Makes bot repeat what you say."""
		await ctx.message.delete()
		await ctx.send(text)

	@commands.command()
	async def nick(self, ctx, *, nick):
		"""Change the bot nickname."""
		await self.bot.user.edit(username=nick)

	@commands.command()
	async def notice(self, ctx, user: discord.Member):
		"""Remove user for ignore list."""

		if user.id not in self.bot.ignore_users:
			return await ctx.send('User was never ignored.')

		self.bot.ignore_users.remove(user.id)

		with open('lib/ignore.json', 'w') as f:
			f.write(json.dumps(self.bot.ignore_users, sort_keys=True, indent=4))

		await ctx.send('User removed from ignore list.')

	@commands.command()
	async def ignore(self, ctx, user: discord.Member):
		"""Add user to ignore list."""

		if user.id in self.bot.ignore_users:
			return await ctx.send('User already ignored.')

		self.bot.ignore_users.append(user.id)

		with open('lib/ignore.json', 'w') as f:
			f.write(json.dumps(self.bot.ignore_users, sort_keys=True, indent=4))

		await ctx.send('User ignored.')

	@commands.command(aliases=['gh'])
	async def github(self, ctx, *, query):
		"""Search for a GitHub repo."""
		await ctx.invoke(self.search, query='site:github.com ' + query)

	@commands.command(aliases=['f'])
	async def forum(self, ctx, *, query):
		"""Search for an AutoHotkey thread."""
		await ctx.invoke(self.search, query='site:https://autohotkey.com/boards/ ' + query)

	@commands.command(aliases=['g'])
	async def search(self, ctx, *, query):
		"""Search Google."""
		"""
		headers = {
			'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36',
			'Accept:': 'text/html'
		}
		params = {'hl': 'en', 'safe': 'on', 'q': query}
		text = await self.bot.request('get', 'http://google.com/search', params=params, headers=headers)
		if text is None:
			return await ctx.send('Request failed.')
		"""
		import requests
		await ctx.trigger_typing()
		req = requests.get('http://google.com/search?hl=en&safe=on&q={}'.format(query))
		result = google_result(req.text)
		if not result:
			await ctx.send('No results.')
		else:
			embed = discord.Embed(title=result['title'], url=result['url'], description=result['description'])
			embed.set_footer(text=result['domain'])
			await ctx.send(embed=embed)

	@commands.command(hidden=True)
	async def evalp(self, ctx, *, body: str):
		await ctx.invoke(self.eval, body=f'print({body})')

	@commands.command(hidden=True)
	async def evals(self, ctx, *, body: str):
		await ctx.invoke(self.eval, body=f'await ctx.send({body})')

	@commands.command(hidden=True)
	async def eval(self, ctx, *, body: str):
		"""Evaluates a code"""

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
	bot.add_cog(Admin(bot))