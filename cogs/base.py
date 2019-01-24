class TogglableCogMixin:
	def __init__(self, bot):
		self.bot = bot
		mod_name = self.__class__.__name__.lower()
		if mod_name not in self.bot._toggleable:
			self.bot._toggleable.append(mod_name)

	async def _is_used(self, ctx):
		return await self.bot.uses_module(ctx.guild.id, self.__class__.__name__)