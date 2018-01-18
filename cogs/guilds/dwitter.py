import discord
from discord.ext import commands

import re
from peewee import *

import datetime

db = SqliteDatabase('lib/dwitter_top.db')

class Dwitter:
	"""Commands for the Dwitter server."""

	def __init__(self, bot):
		self.bot = bot
		self.guilds = (395956681793863690,367975590143459328)

		self.url = 'https://www.dwitter.net/'

	async def __local_check(self, ctx):
		return ctx.guild.id in self.guilds

	async def on_message(self, message):
		# ignore messages that start with a prefix
		if message.content.startswith(tuple(await self.bot.get_prefix(message))):
			return

		# check for correct guild
		if message.guild.id not in self.guilds or self.bot.blacklist(message.author):
			return

		# find dweet shorthands in message
		short = re.findall('.?(d/(\d*)).?', message.content)

		if not len(short):
			return

		seen = []
		for group in short:
			if len(seen) > 1:
				break
			if group[1] not in seen:
				seen.append(group[1])
				await self.dwitterlink(message, group[1])

	async def dwitterlink(self, message, id):
		dweet = await self.bot.request('get', self.url + 'api/dweets/' + id)

		if dweet is None:
			return None

		e = await self.embeddweet(dweet)
		await message.channel.send(embed=e)

		# don't count my own links because I only use it for testing
		if await self.bot.is_owner(message.author):
			return

		try:
			dwit = Dweet.get(Dweet.id == id)
		except Dweet.DoesNotExist:
			dwit = Dweet.create(id=id)

		dwit.count += 1
		dwit.save()

	async def embeddweet(self, dweet):
		e = discord.Embed()

		e.title = dweet['link']
		e.url = dweet['link']
		e.description = f"```js\n{dweet['code']}\n```"

		e.add_field(name='Awesomes', value=dweet['awesome_count'])

		if dweet['remix_of'] is not None:
			remix = str(dweet['remix_of'])
			e.add_field(name='Remix of', value=f"[{remix}]({self.url + 'd/' + remix})")

		author = dweet['author']
		e.set_author(name=author['username'], url=author['link'], icon_url=author['avatar'])

		e.timestamp = datetime.datetime.strptime(dweet['posted'].split('.')[0], "%Y-%m-%dT%H:%M:%S")

		return e

	@commands.command()
	async def top(self, ctx):
		"""Get a list of the most referenced Dweets."""

		list = Dweet.select().order_by(Dweet.count.desc())

		ids, counts = '', ''
		for index, dwit in enumerate(list):
			if (index > 7):
				break
			ids += f'\n[{dwit.id}](https://www.dwitter.net/d/{dwit.id})'
			counts += f'\n{dwit.count}'

		e = discord.Embed()

		e.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)

		e.add_field(name='Dweet', value=ids, inline=True)
		e.add_field(name='Times linked', value=counts, inline=True)

		await ctx.send(embed=e)

	@commands.command(aliases=['site'])
	async def dwitter(self, ctx):
		"""Return a link to the Dwitter site."""
		await ctx.send('https://www.dwitter.net/')


class Dweet(Model):
	id = IntegerField(primary_key=True)
	count = IntegerField(default=0)

	class Meta:
		database = db

def setup(bot):
	db.connect()
	db.create_tables([Dweet], safe=True)
	bot.add_cog(Dwitter(bot))