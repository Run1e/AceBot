
def shorten(text, max_char=2000):
	'''Shortens text to fit within max_chars and max_newline.'''

	if max_char < 16:
		raise ValueError('Only shortens down to 16 characters')

	if max_char >= len(text):
		return text

	text = text[0:max_char - 4]

	for i in range(1, 16):
		if text[-i] in (' ', '\n'):
			return text[0:len(text) - i + 1] + '...'

	return text + ' ...'


def craft_welcome(member, string):
	repl = {
		'guild': member.guild.name,
		'user': member.mention,
		'member_count': member.guild.member_count
	}

	for key, val in repl.items():
		string = string.replace('{' + key + '}', str(val))

	return string
