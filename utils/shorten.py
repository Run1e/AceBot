def shorten(text, max_char, max_newline):
	shortened = False

	if len(text) > max_char:
		text = text[0:max_char]
		shortened = True

	if text.count('\n') > max_newline:
		text = text[0:find_nth(text, '\n', max_newline)]
		shortened = True

	if shortened:
		text = text[0:len(text) - 4] + ' ...'

	return text

def find_nth(haystack, needle, n):
	start = haystack.find(needle)
	while start >= 0 and n > 1:
		start = haystack.find(needle, start + len(needle))
		n -= 1
	return start