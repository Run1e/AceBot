import discord
from discord.ext import commands

import re
from peewee import *

db = SqliteDatabase('lib/dwitter_top.db')

class Dwitter:
	"""Commands for the Dwitter server."""

	def __init__(self, bot):
		self.bot = bot
		self.guilds = (395956681793863690,)

	async def __local_check(self, ctx):
		return ctx.guild.id in self.guilds

	async def on_message(self, message):
		# ignore messages that start with a prefix
		if message.content.startswith(tuple(await self.bot.get_prefix(message))):
			return

		# check for correct guild
		if message.guild.id not in self.guilds or self.bot.blacklist(message.author):
			return

		# find links in message
		try:
			links = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content)
		except:
			return

		# loop through links and send previews if applicable
		seen = []
		for link in links:
			if len(seen) > 2:
				break
			if link in seen:
				continue
			if re.match("^https?://(www.)?dwitter.net/d/\d{2,}$", link):
				seen.append(link)
				await self.dwitterlink(message, link)

	async def dwitterlink(self, message, link):
		split = link.split('/')
		id = split[len(split) - 1]

		try:
			dwit = Dweet.get(Dweet.id == id)
		except Dweet.DoesNotExist:
			dwit = Dweet.create(id=id)

		dwit.count += 1
		dwit.save()

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