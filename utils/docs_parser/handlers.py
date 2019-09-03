import discord
import re

from bs4 import BeautifulSoup, NavigableString

from utils.html2markdown import HTML2Markdown


MULTIPLE_NAME_RE = re.compile(r'.*\[.*\]$')
HEADER_RE = re.compile(r'^h\d$')
DIV_OR_HEADER_RE = re.compile(r'^(div|h\d)$')


class DescAndSyntaxFound(Exception):
	pass


# the base parser looks for all h2 and h3 tags that link somewhere and adds those sites
# it's the most basic way of parsing
class BaseParser:
	DOCS_URL = None
	DOCS_FOLDER = None
	PARSER = 'lxml'

	def __init__(self, page, prefix=None, postfix=None, ignores=None):
		self.page = page
		self.prefix = prefix or ''
		self.postfix = postfix or ''
		self.ignores = ignores or list()
		self.entries = list()

		self.h2m = DocsHTML2Markdown(
			escaper=discord.utils.escape_markdown, base_url=self.DOCS_URL + self.page,
			big_box=False, lang='autoit', max_len=2000
		)

		with open('{}/{}'.format(self.DOCS_FOLDER, self.page), 'r') as f:
			self.bs = BeautifulSoup(f.read(), self.PARSER)

	def _set_prefix_and_prepend(self, name):
		return self.prefix + name + self.postfix

	def add(self, names, page, **kwargs):

		# remove unwanted names
		for name in names:
			if name in self.ignores:
				names.remove(name)
				return

		# if no names left, return
		if not len(names):
			return

		for idx, name in enumerate(names):
			names[idx] = self._set_prefix_and_prepend(name)

		self.add_force(names, page, **kwargs)

	def add_force(self, names, page=None, **kwargs):
		self.entries.append(dict(names=names, page=page, **kwargs))

	def run(self):
		self.go()
		return self.entries

	def add_page_entry(self):
		header = self.bs.find('h1')
		if header is None:
			return
		names = self.as_list(header)

		p = header.find_next_sibling('p')
		if p is None:
			return

		desc = self.as_string(p)
		self.add_force(names=names, page=self.page, desc=desc)

	def as_string(self, tag):
		content = self._as_string_meta(tag)

		if not len(content):
			return None

		return content.strip()

	def _as_string_meta(self, tag):
		if isinstance(tag, NavigableString):
			return str(tag)
		elif tag.name == 'br':
			return '\n'

		content = ''
		for child in tag.children:
			content += self._as_string_meta(child)

		return content

	@staticmethod
	def remove_versioning(tag):
		for span in tag.find_all('span', class_='ver'):
			span.decompose()

	def handle_optional(self, tag):
		for span in tag.find_all('span', class_='optional'):
			span.replace_with('[{}]'.format(self.as_string(span)))

	@staticmethod
	def convert_brs(tag):
		for br in tag.find_all('br'):
			br.replace_with('\n')

	def as_list(self, tag):
		self.remove_versioning(tag)

		names = [self.as_string(tag)]
		splits = [' or ', ' / ', '\n']

		# fragment the names by the splits def above
		for split in splits:
			new_names = list()
			for name in names:
				for insert_name in name.split(split):
					if len(insert_name) and insert_name != '\n':
						if insert_name.endswith(': Send Keys & Clicks'):
							insert_name = insert_name.rstrip(': Send Keys & Clicks')
						new_names.append(insert_name.strip())
			names = new_names

		# also split if we have stuff like Command[OptionalPostfix]
		new_names = list()
		for name in names:
			if not name.startswith('[') and len(name) > 5 and re.match(MULTIPLE_NAME_RE, name):
				bracket_split = name.split('[')
				base = bracket_split[0]
				others = bracket_split[1][:-1]

				new_names.append(base)
				for other_split in others.split('|'):
					new_names.append(base + other_split)
			else:
				new_names.append(name)

		return new_names

	def get_desc_and_syntax(self, tag):
		desc = None
		syntax = None

		def check_name(tg):
			return tg.name in (tag.name, 'p', 'pre')

		def check_tag(sub):
			nonlocal desc, syntax
			if desc is None and sub.name == 'p':
				desc = self.pretty_desc(sub)
			elif syntax is None and sub.name == 'pre':
				self.handle_optional(sub)
				syntax = self.as_string(sub)

			if syntax is not None and desc is not None:
				raise DescAndSyntaxFound()

		try:
			for sub in tag.find_all(check_name):
				check_tag(sub)

			for sib in tag.next_siblings:
				if isinstance(sib, NavigableString):
					continue
				check_tag(sib)
				for sub in sib.find_all(check_name):
					check_tag(sub)
		except DescAndSyntaxFound:
			pass

		return desc, syntax

	def pretty_desc(self, tag):
		self.remove_versioning(tag)
		self.convert_brs(tag)
		md = self.h2m.convert(str(tag))

		sp = md.split('.\n')
		return md[0:len(sp[0]) + 1] if len(sp) > 1 else md


class HeadersParser(BaseParser):
	def handle(self, id, tag):
		names = self.as_list(tag)

		desc, syntax = self.get_desc_and_syntax(tag)

		self.add(names, '{}#{}'.format(self.page, id), desc=desc, syntax=syntax)

	def go(self):
		self.add_page_entry()

		for tag in self.bs.find_all(HEADER_RE, id=True):
			self.handle(tag.get('id'), tag)


class VariablesParser(BaseParser):
	def go(self):
		self.add_page_entry()

		for tr in self.bs.find_all('tr'):
			first = True
			names, desc = None, None
			for td in tr.find_all('td'):
				if first:
					first = False
					names = self.as_list(td)
				else:
					desc = self.pretty_desc(td)

			if names is None:
				continue

			id = tr.get('id')
			self.add(names, self.page if id is None else '{}#{}'.format(self.page, id), desc=desc)


class MethodListParser(BaseParser):
	def go(self):
		self.add_page_entry()

		for tag in self.bs.find_all('div', id=True):
			id = tag.get('id')
			names = self.as_list(tag.find('h2'))

			desc, syntax = self.get_desc_and_syntax(tag)

			self.add(names, '{}#{}'.format(self.page, id), desc=desc, syntax=syntax)


class CommandParser(BaseParser):
	def go(self):
		body = self.bs.find('body')

		header = body.find('h1')
		if header is None:
			return

		names = self.as_list(header)
		desc, syntax = self.get_desc_and_syntax(body)
		self.add(names, self.page, desc=desc, syntax=syntax)


class EnumeratorParser(HeadersParser):
	def go(self):
		self.add_page_entry()

		for tag in self.bs.find_all('h2', id=True):
			self.handle(tag.get('id'), tag)


class GuiControlParser(HeadersParser):
	def _set_prefix_and_prepend(self, name):
		if ' ' in name or '_' in name:
			return name
		return super()._set_prefix_and_prepend(name)


class DocsHTML2Markdown(HTML2Markdown):
	def codebox(self, tag):
		if tag.name == 'pre':
			old_bigbox = self.big_box
			self.big_box = True
			front, back = self._codebox_wraps()
			self.big_box = old_bigbox
		else:
			front, back = self._codebox_wraps()

		# specific fix for autohotkey rss
		for br in tag.find_all('br'):
			br.replace_with('\n')

		contents = self._get_content(tag)
		self.result.add_and_consume(front + contents + back)


class DocsAggregator:
	def __init__(self):
		self.names = list()
		self.entries = list()

	async def get_all(self):
		for entry in self.entries:
			yield entry

	def name_check(self, name):
		name = name.lower()

		if name in self.names:
			return False

		if name.endswith('()') and name[:-2] in self.names:
			return False

		return True

	def get_entry_by_page(self, page):
		for entry in self.entries:
			if entry['page'] == page:
				return entry
		return None

	def add_entry(self, entry):
		if entry.get('page') is None:
			raise ValueError('Page should not be None. Names: {}'.format(entry.get('names')))

		to_remove = list()
		for idx, name in enumerate(entry['names']):
			if not self.name_check(name):
				to_remove.append(idx)

		for idx in reversed(to_remove):
			entry['names'].pop(idx)

		if not len(entry['names']):
			return

		for name in entry['names']:
			self.names.append(name.lower())

		similar_entry = self.get_entry_by_page(entry['page'])
		if similar_entry is None:
			self.entries.append(entry)
		else:
			for name in filter(lambda name: name not in similar_entry['names'], entry['names']):
				similar_entry['names'].append(name)
