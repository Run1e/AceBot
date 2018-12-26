from math import floor

def pretty_seconds(s):
	hours, remainder = divmod(s, 3600)
	minutes, seconds = divmod(remainder, 60)

	seconds = floor(seconds)
	minutes = floor(minutes)
	hours = floor(hours)

	parts = []

	if hours > 0:
		parts.append(str(hours) + ' hours')

	if minutes > 0:
		parts.append(str(minutes) + ' minutes')

	if not len(parts):
		parts.append(str(seconds) + ' seconds')

	return ', '.join(parts)