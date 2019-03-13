from math import floor

def pretty_datetime(dt):
	return dt.__format__('%d/%m/%y %H:%M:%S')

def pretty_timedelta(td):
	return pretty_seconds(td.total_seconds())

def pretty_seconds(s):
	years, remainder = divmod(s, 31536000)
	days, remainder = divmod(remainder, 86400)
	hours, remainder = divmod(remainder, 3600)
	minutes, seconds = divmod(remainder, 60)

	seconds = floor(seconds)
	minutes = floor(minutes)
	hours = floor(hours)
	days = floor(days)
	years = floor(years)

	parts = []

	def add_part(type, value):
		parts.append('{} {}{}'.format(str(value), type, 's' if value > 1 else ''))

	if years > 0:
		add_part('year', years)

	if days > 0:
		add_part('day', days)

	if hours > 0 and len(parts) != 2:
		add_part('hour', hours)

	if minutes > 0 and len(parts) != 2:
		add_part('minute', minutes)

	if not len(parts):
		add_part('second', seconds)

	return ', '.join(parts)
