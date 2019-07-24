
# TODO: make a smarter version of this
def shorten(text, max_char, max_newline):
	shortened = False

	if max_char is not None and len(text) > max_char:
		text = text[0:max_char]
		shortened = True

	if max_newline is not None and text.count('\n') > max_newline:
		text = text[0:find_nth(text, '\n', max_newline)]
		shortened = True

	if shortened:
		text = text[0:len(text) - 3] + '...'

	return text


def find_nth(haystack, needle, n):
	start = haystack.find(needle)
	while start >= 0 and n > 1:
		start = haystack.find(needle, start + len(needle))
		n -= 1
	return start


def craft_welcome(member, string):
	repl = {
		'guild': member.guild.name,
		'user': member.mention,
		'member_count': member.guild.member_count
	}

	for key, val in repl.items():
		string = string.replace('{' + key + '}', str(val))

	return string
