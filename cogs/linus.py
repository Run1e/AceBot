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

class Linus(AceMixin, commands.Cog):
    async def get_rant_for_phrase(self, ctx, phrase):
        if phrase in LINUS_PHRASES_TO_HATE:
            hate = LINUS_PHRASES_TO_HATE[phrase]
        else:
            hate = 9

        rant = await self.db.fetchval('SELECT rant FROM linus_rant WHERE (hate >= ($1) AND hate <= ($1 + 0.1)) ORDER BY random() LIMIT 1', float(hate) / 10)
		
        rant_embed = discord.Embed(title='Linus is very unhappy with you.')

        rant_embed.set_author(
            name='Linus Torvalds', 
            url=LINUS_GITHUB_URL, 
            icon_url=LINUS_GITHUB_ICON_URL
        )

        rant_embed.add_field(
            name='Rant', 
            value= await commands.clean_content(escape_markdown=True).convert(ctx, rant)
        )

        rant_embed.set_footer(
            text= 'Hate Level: {}%'.format(hate * 10)
        )

        return rant_embed

    @commands.command()
    async def linus(self, ctx, *, words):
        '''Get a random Linus rant. Words = a phrase which will decide which level of hate the quote will have.'''

        await ctx.send(embed=await self.get_rant_for_phrase(ctx, words.lower()))

    @commands.command()
    async def harder(self, ctx, should_only_be_linus: str):
        if should_only_be_linus.lower() != 'linus':
            return

        await ctx.send(embed=await self.get_rant_for_phrase(ctx, 'harder'))

def setup(bot):
	bot.add_cog(Linus(bot))
