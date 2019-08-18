from discord.ext import commands
from datetime import timedelta


class TimeMultConverter(commands.Converter):
	async def convert(self, ctx, mult):
		try:
			mult = float(mult)
		except ValueError:
			raise commands.CommandError('Argument has to be float.')

		if mult < 1.0:
			raise commands.CommandError('Unit must be more than 1.')

		return mult


class TimeDeltaConverter(commands.Converter):
	async def convert(self, ctx, unit):
		unit = unit.lower()

		if unit in ('s', 'sec', 'secs', 'second', 'seconds'):
			return timedelta(seconds=1)
		elif unit in ('m', 'min', 'mins', 'minute', 'minutes'):
			return timedelta(minutes=1)
		elif unit in ('h', 'hr', 'hrs', 'hour', 'hours'):
			return timedelta(hours=1)
		elif unit in ('d', 'day', 'days'):
			return timedelta(days=1)
		elif unit in ('w', 'wk', 'week', 'weeks'):
			return timedelta(weeks=1)
		else:
			raise commands.BadArgument('Unknown time type.')
