from discord.ext import commands


class Int32Converter(commands.Converter):
	MAX = pow(2, 31) - 1

	async def convert(self, ctx, value):
		try:
			value = int(value)
		except ValueError:
			raise commands.CommandError('Value not an integer.')

		if value > self.MAX:
			raise commands.CommandError('Value out of bounds.')

		return value
