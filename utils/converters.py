from inspect import Parameter

import emoji
from discord.ext import commands

empty = Parameter.empty


def param_name(converter, ctx):
	fallback = 'Argument'

	for param_name, parameter in ctx.command.params.items():
		param_conv = parameter.annotation

		if param_conv == empty:
			continue

		if param_conv is converter:
			return param_name

	return fallback


def _make_int(converter, ctx, argument):
	try:
		return int(argument)
	except ValueError:
		name = param_name(converter, ctx)
		raise commands.BadArgument(f'{name} should be a number.')


class EmojiConverter(commands.Converter):
	async def convert(self, ctx, argument):
		guild_emojis = list(str(e) for e in ctx.guild.emojis)

		if argument not in emoji.UNICODE_EMOJI:
			if argument not in guild_emojis:
				raise commands.BadArgument('Unknown emoji.')

		return argument


class MaxValueConverter(commands.Converter):
	def __init__(self, _max):
		self.max = _max

	async def convert(self, ctx, argument):
		value = _make_int(self, ctx, argument)

		if value > self.max:
			name = param_name(self, ctx)
			raise commands.BadArgument(f'{name} must be lower than {self.max}')

		return value


class SerialConverter(commands.Converter):
	MAX = pow(2, 31) - 1

	async def convert(self, ctx, argument):
		value = _make_int(self, ctx, argument)

		if value > self.MAX:
			name = param_name(self, ctx)
			raise commands.BadArgument(f'{name} must be a lower value.')

		return value


class RangeConverter(commands.Converter):
	def __init__(self, min, max):
		self.min = min
		self.max = max

	def _make_error(self, ctx):
		name = param_name(self, ctx)
		return commands.BadArgument(f'{name} must be between {self.min} and {self.max}')

	async def convert(self, ctx, argument):
		value = _make_int(self, ctx, argument)

		if value < self.min:
			raise self._make_error(ctx)

		if value > self.max:
			raise self._make_error(ctx)

		return value


class LengthConverter(commands.Converter):
	def __init__(self, min=1, max=32):
		self.min = min
		self.max = max

	def _make_error(self, ctx):
		name = param_name(self, ctx)
		return commands.BadArgument(f'{name} must be between {self.min} and {self.max} characters.')

	async def convert(self, ctx, argument):
		length = len(argument)

		if length < self.min:
			raise self._make_error(ctx)

		if length > self.max:
			raise self._make_error(ctx)

		return argument


class MaxLengthConverter(commands.Converter):
	def __init__(self, max=32):
		self.max = max

	async def convert(self, ctx, argument):
		length = len(argument)

		if length > self.max:
			name = param_name(self, ctx)
			raise commands.BadArgument(f'{name} must be shorter than {self.max} characters.')

		return argument
