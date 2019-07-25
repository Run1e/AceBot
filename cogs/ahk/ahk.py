import discord
import logging

from discord.ext import commands, tasks


from cogs.mixins import AceMixin
from utils.docs_parser import parse_docs
from utils.html2markdown import html2markdown


class AutoHotkey(AceMixin, commands.Cog):
	'''Commands for the AutoHotkey guild.'''

	def __init__(self, bot):
		super().__init__(bot)

		# start rss

	@commands.command(hidden=True)
	@commands.is_owner()
	async def build(self, ctx, download: bool = True):
		async def on_update(text):
			await ctx.send(text)

		async def handler(names, page, desc=None, syntax=None, params=None):

			# ignore everything that has to do with examples
			for name in names:
				if 'example' in name.lower():
					return

			docs_id = await self.db.fetchval('SELECT id FROM docs_entry WHERE page=$1', page)

			if docs_id is None:
				docs_id = await self.db.fetchval(
					'INSERT INTO docs_entry (page, content) VALUES ($1, $2) RETURNING id',
					page, desc
				)

			for name in names:
				# don't add if item already exists (including case insensitive matches)
				if await self.db.fetchval('SELECT id FROM docs_name WHERE LOWER(name)=$1', name.lower()):
					continue
				if name.endswith('()') and await self.db.fetchval('SELECT id FROM docs_name WHERE LOWER(name)=$1', name.lower()[:-2]):
					continue
				await self.db.execute('INSERT INTO docs_name (docs_id, name) VALUES ($1, $2)', docs_id, name)

			if syntax is not None:
				await self.db.execute('INSERT INTO docs_syntax (docs_id, syntax) VALUES ($1, $2)', docs_id, syntax)

			if params is not None:
				for name, value in params.items():
					await self.db.execute(
						'INSERT INTO docs_param (docs_id, name, value) VALUES ($1, $2, $3)',
						docs_id, name, value
					)

		await self.db.execute('TRUNCATE docs_name, docs_syntax, docs_param, docs_entry RESTART IDENTITY')

		#try:
		await parse_docs(handler, on_update, download)
		#except Exception as exc:
		#	raise commands.CommandError(str(exc))

	@commands.command()
	async def version(self, ctx):
		'''Get changelog and download for the latest AutoHotkey_L version.'''

		url = 'https://api.github.com/repos/Lexikos/AutoHotkey_L/releases'

		async with self.bot.aiohttp.request('get', url) as resp:
			if resp.status != 200:
				raise commands.CommandError('Query failed.')

			js = await resp.json()

		latest = js[0]
		asset = latest['assets'][0]

		e = discord.Embed(
			description='Update notes:\n```\n' + latest['body'] + '\n```'
		)

		e.set_author(
			name='AutoHotkey_L ' + latest['name'],
			icon_url=latest['author']['avatar_url']
		)

		e.add_field(name='Release page', value=f"[Click here]({latest['html_url']})")
		e.add_field(name='Installer download', value=f"[Click here]({asset['browser_download_url']})")
		e.add_field(name='Downloads', value=asset['download_count'])

		await ctx.send(embed=e)


def setup(bot):
	bot.add_cog(AutoHotkey(bot))
