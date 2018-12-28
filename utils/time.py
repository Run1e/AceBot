from math import floor

def pretty_seconds(s):
	hours, remainder = divmod(s, 3600)
	minutes, seconds = divmod(remainder, 60)

	seconds = floor(seconds)
	minutes = floor(minutes)
	hours = floor(hours)

	parts = []

	def add_part(type, value):
		parts.append('{} {}{}'.format(str(value), type, 's' if value > 1 else ''))

	if hours > 0:
		add_part('hour', hours)

	if minutes > 0:
		add_part('minute', minutes)

	if not len(parts):
		add_part('second', seconds)

	return ', '.join(parts)