import re
from bs4 import BeautifulSoup, NavigableString

PREPEND = dict(
	br='\n',  # linebreak
)

PREPEND_LINES = dict(
	blockquote='> '
)

WRAP = dict(
	b='**',  # bold
	em='*',  # emphasis
	i='*',  # italics
)

MULTIWRAP = dict(
	li=(' • ', '\n'),  # list item
)

SPACING = dict(
	p=2,
	div=2,
	ul=2
)

CODEBOX_NAMES = ('code', 'pre')


class CreditsEmpty(Exception):
	pass


class Result:
	def __init__(self, credits):
		self.credits = credits
		self.content = ''
		self.prepender = None

	def __str__(self):
		return self.content

	def consume(self, amount: int):
		if amount > self.credits:
			raise CreditsEmpty()

		self.credits -= amount

	def feed(self, amount: int):
		self.credits += amount

	def can_afford(self, string):
		return len(string) <= self.credits

	def ensure_spacing(self, spacing=2):
		while self.content.endswith('\n' * (spacing + 1)):
			self.content = self.content[:-1]
			self.feed(1)

		while not self.content.endswith('\n' * spacing):
			self.content += '\n'
			self.consume(1)

	def add(self, string):
		self.content += string

	def add_and_consume(self, string, trunc=False):
		if self.prepender is not None and string != '\n':
			string = '\n'.join('{}{}'.format(self.prepender, text) for text in string.split('\n') if len(text))

		to_consume = len(string)
		do_raise = False

		if trunc is True and to_consume > self.credits:
			to_consume = self.credits
			string = string[:to_consume]
			do_raise = True

		self.consume(to_consume)
		self.add(string)

		if do_raise:
			raise CreditsEmpty()

	def set_prepend(self, prepender):
		self.prepender = prepender

	def clear_prepend(self):
		self.prepender = None


class HTML2Markdown:
	def __init__(self, escaper=None, big_box=False, lang=None, max_len=2000, base_url=None):
		self.result = None
		self.escaper = escaper
		self.max_len = max_len
		self.base_url = base_url
		self.big_box = big_box
		self.lang = lang

		self.cutoff = '...'

	def convert(self, html, temp_url=None):
		self.result = Result(max(self.max_len, 8) - len(self.cutoff) - 1)

		if temp_url is not None:
			old_url = self.base_url
			self.base_url = temp_url
		else:
			old_url = None

		try:
			self.traverse(BeautifulSoup(html, 'html.parser'))
		except CreditsEmpty:
			if str(self.result).endswith(' '):
				self.result.add(self.cutoff)
			else:
				self.result.add(' ' + self.cutoff)

		if old_url is not None:
			self.base_url = old_url

		ret = str(self.result)

		ret = re.sub('\n\n+', '\n\n', ret)
		ret = re.sub('\n```\n+', '\n```\n', ret)

		return ret.strip('\n')

	def traverse(self, tag):
		for node in tag.contents:
			if isinstance(node, NavigableString):
				self.navigable_string(node)
			else:
				if node.name in CODEBOX_NAMES:
					self.codebox(node)
					continue
				elif node.name == 'a':
					self.link(node)
					continue

				back_required = False

				if node.name in PREPEND:
					front, back = PREPEND[node.name], ''

				elif node.name in WRAP:
					wrap_str = WRAP[node.name]
					front, back = wrap_str, wrap_str

					# for wrapping, we *must* add the back char(s)
					back_required = True

				elif node.name in MULTIWRAP:
					front, back = MULTIWRAP[node.name]

				else:
					front, back = '', ''

				# if we can't add the front + back and at least one char, just raise creditsempty
				if not self.result.can_afford(front + back + ' '):
					raise CreditsEmpty()

				self.result.add_and_consume(front)

				# prematurely consume the back characters if it *must* be added later
				if back_required:
					self.result.consume(len(back))

				if node.name in PREPEND_LINES:
					prepend_all_mode = True
					self.result.set_prepend(PREPEND_LINES[node.name])
				else:
					prepend_all_mode = False

				try:
					self.traverse(node)
				except CreditsEmpty as exc:
					if back_required:
						self.result.add(back)
					raise exc

				if prepend_all_mode:
					self.result.clear_prepend()

				if back_required:
					self.result.add(back)
				else:
					if node.name in SPACING:
						self.result.ensure_spacing(SPACING[node.name])
					else:
						self.result.add_and_consume(back)

	def navigable_string(self, node):
		content = str(node)
		self.result.add_and_consume(self.escaper(content) if callable(self.escaper) else content, True)

	def get_content(self, tag):
		content = self._get_content_meta(tag)
		return content.strip()

	def _get_content_meta(self, tag):
		if isinstance(tag, NavigableString):
			return str(tag)
		elif tag.name == 'br':
			return '\n'

		content = ''
		for child in tag.children:
			content += self._get_content_meta(child)

		return content

	def codebox(self, tag):
		front, back = self._codebox_wraps()

		# specific fix for autohotkey rss
		for br in tag.find_all('br'):
			br.replace_with('\n')

		contents = self.get_content(tag)

		self.result.add_and_consume(front + contents + back)

	def _codebox_wraps(self):
		return '```{}\n'.format(self.lang or '') if self.big_box else '`', '\n```\n' if self.big_box else '`'

	def link(self, tag):
		credits = self.result.credits

		link = self._format_link(tag['href'])
		contents = self.get_content(tag)

		full = '[{}]({})'.format(contents, link)

		if link is None:
			self.result.add_and_consume(contents, True)
		elif credits >= len(full):
			self.result.add_and_consume(full)
		elif credits >= len(link) + 5:
			self.result.add_and_consume('[{}]({})'.format(contents[:credits - len(link) - 4], link))
		else:
			self.result.add_and_consume(contents, True)

	def _format_link(self, href):
		if re.match(r'^.+:\/\/', href):
			return href

		if self.base_url is None:
			return None

		if href.startswith('#'):
			return self.base_url + href
		else:
			return '/'.join(self.base_url.split('/')[:-1]) + '/' + href
