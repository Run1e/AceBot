import discord
from discord.ext import commands

from cogs.mixins import AceMixin

LINUS_PHRASES_TO_HATE = {'destroy me': 9, 'ruin me': 8, 'harder': 7, 'please': 7, 'give it to me': 6, 'go slow': 5, 'gently': 4}

class Linus(AceMixin, commands.Cog):
    async def get_rant_for_phrase(self, ctx, phrase):
        if phrase in LINUS_PHRASES_TO_HATE:
            hate = LINUS_PHRASES_TO_HATE[phrase]
        else:
            hate = 9

        rant_text = (await self.db.fetchrow('SELECT * FROM linus_rants WHERE (hate >= ($1) AND hate <= ($1 + 0.1)) ORDER BY random() LIMIT 1', float(hate) / 10)).get('rant')
        rant_length = len(rant_text)

        if rant_length >= 2000:
            rant_text = '{}...'.format(rant_text[0:min(rant_length, 2000) - 4])

        return await (commands.clean_content(escape_markdown=True)).convert(ctx, rant_text)

    @commands.command()
    async def linus(self, ctx, *words: str):
        '''Get a random linus rant.'''

        await ctx.send(await self.get_rant_for_phrase(ctx, ' '.join(words).lower()))

    @commands.command()
    async def harder(self, ctx, should_only_be_linus: str):
        if (should_only_be_linus.lower() != 'linus'):
            return

        await ctx.send(await self.get_rant_for_phrase(ctx, 'harder'))

def setup(bot):
	bot.add_cog(Linus(bot))
