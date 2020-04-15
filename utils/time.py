import math

from discord.ext import commands
from datetime import datetime, timedelta


ordinal = lambda n: "%d%s" % (n,"tsnrhtdd"[(math.floor(n/10)%10!=1)*(n%10<4)*n%10::4])


steps = dict(
	year=timedelta(days=365),
	week=timedelta(days=7),
	day=timedelta(days=1),
	hour=timedelta(hours=1),
	minute=timedelta(minutes=1),
	second=timedelta(seconds=1),
	millisecond=timedelta(milliseconds=1)
)


def pretty_timedelta(td: timedelta):
	'''Returns a pretty string of a timedelta'''

	if not isinstance(td, timedelta):
		raise ValueError('timedelta expected, \'{}\' given'.format(type(td)))

	parts = []

	for name, span in steps.items():
		if td >= span:
			count = int(td / span)
			td -= count * span
			parts.append('{} {}{}'.format(count, name, 's' if count > 1 else ''))
			if len(parts) >= 2 or name == 'second':
				break
		elif len(parts):
			break

	return ', '.join(parts)


def pretty_seconds(s):
	return pretty_timedelta(timedelta(seconds=s))


def pretty_datetime(dt: datetime, ignore_time=False):
	if not isinstance(dt, datetime):
		raise ValueError('datetime expected, \'{}\' given'.format(type(dt)))

	return '{0} {1}'.format(ordinal(int(dt.strftime('%d'))), dt.strftime('%b %Y' + ('' if ignore_time else ' %H:%M')))


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
