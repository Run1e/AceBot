import discord, re, datetime
from discord.ext import commands


class Dwitter:
	"""Commands for the Dwitter server."""

	def __init__(self, bot):
		self.bot = bot

		self.url = 'https://www.dwitter.net/'
		self.guilds = (395956681793863690, 517692823621861407)

	async def __local_check(self, ctx):
		return getattr(ctx.guild, 'id', None) in self.guilds

	async def on_message(self, message):
		# guild check
		if not await self.__local_check(message):
			return

		# ignore messages that start with a prefix
		if message.author.bot or message.content.startswith(tuple(await self.bot.get_prefix(message))):
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
		dweet = None

		async with self.bot.aiohttp.get(self.url + 'api/dweets/' + id) as resp:
			if resp.status != 200:
				return
			dweet = await resp.json()

		if dweet is None or 'link' not in dweet:
			return None

		e = await self.embeddweet(dweet)
		await message.channel.send(embed=e)

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

	@commands.command(aliases=['site'])
	async def dwitter(self, ctx):
		"""Return a link to the Dwitter site."""
		await ctx.send('https://www.dwitter.net/')


def setup(bot):
	bot.add_cog(Dwitter(bot))
