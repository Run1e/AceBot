from math import floor

def pretty_seconds(s):
	days, remainder = divmod(s, 86400)
	hours, remainder = divmod(remainder, 3600)
	minutes, seconds = divmod(remainder, 60)

	seconds = floor(seconds)
	minutes = floor(minutes)
	hours = floor(hours)
	days = floor(days)

	parts = []

	def add_part(type, value):
		parts.append('{} {}{}'.format(str(value), type, 's' if value > 1 else ''))

	if days > 0:
		add_part('day', days)

	if hours > 0:
		add_part('hour', hours)

	if minutes > 0 and len(parts) != 2:
		add_part('minute', minutes)

	if not len(parts):
		add_part('second', seconds)

	return ', '.join(parts)