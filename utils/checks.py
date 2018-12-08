from discord.ext.commands import check

# invoker is either bot owner or guild owner
def is_manager():
	def predicate(ctx):
		return ctx.author.permissions_in(ctx.channel).manage_guild or ctx.author.id == ctx.bot.owner_id
	return check(predicate)