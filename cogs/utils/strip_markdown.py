import re

def strip_markdown(content):
	transformations = {
		re.escape(c): '\\' + c
		for c in ('*', '`', '_', '~', '\\', '<')
	}

	def replace(obj):
		return transformations.get(re.escape(obj.group(0)), '')

	pattern = re.compile('|'.join(transformations.keys()))
	return pattern.sub(replace, content)