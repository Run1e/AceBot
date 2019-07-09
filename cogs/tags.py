import discord
from discord.ext import commands

from cogs.mixins import AceMixin

# todo: TagConverter. checks tag exists (and user can modify it) and returns the asyncpg.Record instance of it
class TagConverter(commands.Converter):
	async def convert(self, ctx, argument):
		pass

class Tags(AceMixin, commands.Cog):
	pass