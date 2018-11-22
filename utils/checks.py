from discord.ext.commands import check

# invoker is either bot owner or guild owner
def bot_or_guild_owner():
	def predicate(ctx):
		return ctx.author.permissions_in(ctx.channel).manage_guild or ctx.author.id == ctx.bot.owner_id
	return check(predicate)