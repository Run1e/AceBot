from datetime import datetime, timedelta

steps = dict(
	year=timedelta(days=365),
	week=timedelta(days=7),
	day=timedelta(days=1),
	hour=timedelta(hours=1),
	minute=timedelta(minutes=1),
	second=timedelta(seconds=1)
)


def pretty_timedelta(td):
	'''Returns a pretty string of a timedelta'''

	if not isinstance(td, timedelta):
		raise ValueError('timedelta expected, \'{}\' given'.format(type(td)))

	parts = []

	for name, span in steps.items():
		if td > span:
			count = int(td / span)
			td -= count * span
			parts.append('{} {}{}'.format(count, name, 's' if count > 1 else ''))
		elif len(parts):
			break

	return ', '.join(parts)


def pretty_seconds(s):
	return pretty_timedelta(timedelta(seconds=s))


def pretty_datetime(dt):
	'''Simply removes the microseconds from the timedelta string.'''

	if not isinstance(dt, datetime):
		raise ValueError('datetime expected, \'{}\' given'.format(type(dt)))

	return str(dt).split('.')[0]
