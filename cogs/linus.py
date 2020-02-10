import discord
from discord.ext import commands

from cogs.mixins import AceMixin

LINUS_PHRASES_TO_HATE = {
	'destroy me': 9,
	'ruin me': 8,
	'harder': 7,
	'please': 7,
	'give it to me': 6,
	'go slow': 5,
	'gently': 4
}

LINUS_GITHUB_URL = 'https://github.com/torvalds'
LINUS_GITHUB_ICON_URL = 'https://avatars1.githubusercontent.com/u/1024025'


class HarshnessConverter(commands.Converter):
	async def convert(self, ctx, harshness):
		return LINUS_PHRASES_TO_HATE.get(harshness, None)


class Linus(AceMixin, commands.Cog):
	async def get_rant_for_phrase(self, ctx, hate):
		if hate is None:
			rant = await self.db.fetchrow('SELECT * FROM linus_rant ORDER BY random() LIMIT 1')
		else:
			rant = await self.db.fetchrow(
				'SELECT * FROM linus_rant WHERE $1 < hate and hate < $1 + 0.1 ORDER BY random() LIMIT 1',
				float(hate) / 10.0
			)

		# set as description so we have 2000 chars to play with
		rant_embed = discord.Embed(
			description=await commands.clean_content(escape_markdown=True).convert(ctx, rant.get('rant'))
		)

		rant_embed.set_author(
			name='Linus Torvalds',
			url=LINUS_GITHUB_URL,
			icon_url=LINUS_GITHUB_ICON_URL
		)

		rant_embed.set_footer(text='Hate Level: {}%'.format(round(rant.get('hate') * 100)))

		return rant_embed

	@commands.command(hidden=True)
	async def linus(self, ctx, *, harshness: HarshnessConverter = None):
		'''Get a random Linus rant.'''

		await ctx.send(embed=await self.get_rant_for_phrase(ctx, harshness))

	@commands.command(hidden=True)
	async def harder(self, ctx, should_only_be_linus: str):
		if should_only_be_linus.lower() != 'linus':
			return

		await ctx.invoke(self.linus, harshness=7)


def setup(bot):
	bot.add_cog(Linus(bot))
