import disnake
import re

from disnake.ext import commands
from datetime import datetime
from collections import OrderedDict
from itertools import islice

from cogs.mixins import AceMixin


class Dwitter(AceMixin, commands.Cog):
    """Commands for the Dwitter server."""

    def __init__(self, bot):
        super().__init__(bot)

        self.url = "https://www.dwitter.net/"
        self.guilds = (395956681793863690, 517692823621861407)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None or message.author.bot:
            return

        if message.guild.id not in self.guilds:
            return

        short = OrderedDict.fromkeys(re.findall(r".?(d/(\d*)).?", message.content))

        for group in islice(short.keys(), 0, 2):
            await self.dwitterlink(message, group[1])

    async def dwitterlink(self, message, id):
        async with self.bot.aiohttp.get(self.url + "api/dweets/" + id) as resp:
            if resp.status != 200:
                return

            dweet = await resp.json()

        if "link" not in dweet:
            return

        e = await self.embeddweet(dweet)

        try:
            await message.channel.send(embed=e)
        except disnake.HTTPException:
            pass

    async def embeddweet(self, dweet):
        e = disnake.Embed(description="```js\n{}\n```".format(dweet["code"]))

        e.add_field(name="Awesomes", value=dweet["awesome_count"])
        e.add_field(name="Link", value="[d/{}]({})".format(dweet["id"], dweet["link"]))

        remix_of = dweet["remix_of"]

        if remix_of is not None:
            e.add_field(
                name="Remix of",
                value="[d/{}]({})".format(remix_of, self.url + "d/" + str(remix_of)),
            )

        author = dweet["author"]
        e.set_author(name=author["username"], url=author["link"], icon_url=author["avatar"])

        e.set_footer(text="Posted")
        e.timestamp = datetime.strptime(dweet["posted"].split(".")[0], "%Y-%m-%dT%H:%M:%S")

        return e


def setup(bot):
    bot.add_cog(Dwitter(bot))
