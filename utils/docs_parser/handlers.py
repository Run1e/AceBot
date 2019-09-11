import discord
import re

from bs4 import BeautifulSoup, NavigableString
from enum import Enum

from utils.html2markdown import HTML2Markdown


MULTIPLE_NAME_RE = re.compile(r'.*\[.*].*')
HEADER_RE = re.compile(r'^h\d$')
DIV_OR_HEADER_RE = re.compile(r'^(div|h\d)$')

DONT_REMOVE_BRACKETS = ('func.()', '%func%()')


class SearchAction(Enum):
	CONTINUE = 1
	LIMIT = 2
	STOP = 3


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

	def add(self, fill_names=None, force_names=None, page=None, desc=None, syntax=None):

		#if page is None:
		#	raise ValueError('Page is none for names ', fill_names, force_names)

		fill_names = list() if fill_names is None else fill_names
		force_names = list() if force_names is None else force_names

		# remove unwanted names
		for name in fill_names:
			if name in self.ignores:
				fill_names.remove(name)
				return

		for idx, name in enumerate(fill_names):
			fill_names[idx] = self._set_prefix_and_prepend(name)
		for idx, name in enumerate(force_names):
			force_names[idx] = self._set_prefix_and_prepend(name)

		self.add_force(fill_names=fill_names, force_names=force_names, page=page, desc=desc, syntax=syntax)

	def add_force(self, **kwargs):
		self.entries.append(dict(**kwargs))

	def run(self):
		self.go()
		return self.entries

	def add_page_entry(self):
		header = self.bs.find('h1')
		if header is None:
			return

		names = self.tag_as_names(header)

		names.append(self.pretty_file_name())

		desc, syntax = self.get_desc_and_syntax(header)

		self.add_force(fill_names=list(), force_names=names, page=self.page, desc=desc)

	def pretty_file_name(self):
		finish = lambda name: re.sub(r' +', ' ', name).strip()

		file_name = self.page.split('/')
		file_name = file_name[len(file_name) - 1][:-4]

		skip_auto_spacing = ('ListView', 'TreeView', 'RegEx', 'AutoIt', 'WinTitle', 'SendMessage')

		replacements = {
			'_': ' ',
			'-': ' ',
		}

		add_trailing_space = ('DBGP', 'AutoIt2', 'RegEx', 'SendMessage')

		for old, new in replacements.items():
			file_name = file_name.replace(old, new)

		for add_spacer in add_trailing_space:
			file_name = file_name.replace(add_spacer, add_spacer + ' ')

		for ignore in skip_auto_spacing:
			if ignore in file_name:
				return finish(file_name)

		since_last = 0
		name = ''
		for letter in file_name:
			if letter.isupper():
				if since_last > 0 and not name.endswith(' '):
					name += ' '
				since_last = 0
			else:
				since_last += 1

			name += letter

		return finish(name)

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

	@staticmethod
	def remove_headnote(tag):
		for span in tag.find_all('span', class_='headnote'):
			span.decompose()

	def handle_optional(self, tag):
		for span in tag.find_all('span', class_='optional'):
			span.replace_with('[{}]'.format(self.as_string(span)))

	@staticmethod
	def convert_brs(tag):
		for br in tag.find_all('br'):
			br.replace_with('\n')

	def _string_as_names(self, name):
		names = [name]
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

		# transform 'a[b|c]d' into ['ad', 'abd', 'acd']
		new_names = list()
		for name in names:
			if not name.startswith('[') and len(name) > 5 and re.match(MULTIPLE_NAME_RE, name):
				bracket_split = name.split('[')
				pre = bracket_split[0]
				bracket2_split = bracket_split[1].split(']')
				others = bracket2_split[0]
				post = '' if len(bracket2_split) == 1 else bracket2_split[1]

				new_names.append((pre[:-1] if pre.endswith(' ') and post.startswith(' ') else pre) + post)
				for other_split in others.split('|'):
					new_name = pre + other_split + post
					new_names.append(new_name)
			else:
				new_names.append(name)

		names = new_names

		# remove trailing '()'
		new_names = list()
		for name in names:
			name = name.strip()
			if name not in DONT_REMOVE_BRACKETS and name.endswith('()'):
				name = name[:-2]
			new_names.append(name)

		names = new_names

		# if on 'thing (asd)' then also add 'thing'
		new_names = list()
		for name in names:
			if '(' in name:
				new_names.append(name.split('(')[0].strip())
			new_names.append(name)

		return new_names

	def tag_as_names(self, tag):
		self.remove_versioning(tag)
		self.remove_headnote(tag)
		return self._string_as_names(self.as_string(tag))

	def get_desc_and_syntax(self, tag):
		desc = None
		syntax = None

		stop_on_tag_name = [tag.name]
		use_on_tag_name = ['pre', 'p']

		if re.fullmatch(HEADER_RE, tag.name):
			current_h = int(tag.name[-1]) - 1
			while current_h > 0:
				stop_on_tag_name.append('h' + str(current_h))
				current_h -= 1

		all_tag_name = use_on_tag_name + stop_on_tag_name

		def pred(pred_tag):
			return pred_tag.name in all_tag_name

		def tag_process(current_tag):
			nonlocal desc, syntax

			if desc is None and current_tag.name == 'p' and current_tag.get('class') is None:
				desc = self.pretty_desc(current_tag)

			if syntax is None and current_tag.name == 'pre':
				self.handle_optional(current_tag)
				self.remove_versioning(current_tag)
				syntax = self.as_string(current_tag)

			if desc is not None and syntax is not None:
				return SearchAction.STOP
			elif current_tag.name in stop_on_tag_name and current_tag != tag:
				return SearchAction.LIMIT
			else:
				return SearchAction.CONTINUE

		self.search(tag, pred, tag_process)
		return desc, syntax

	def search(self, tag, pred, on_found, max_depth=5):
		self._search_meta([tag, *list(tag.next_siblings)], pred, on_found, max_depth, 0)

	def _search_meta(self, tags, pred, on_found, max_depth, current_depth):
		new_tags = list()

		for tag in tags:
			if isinstance(tag, NavigableString):
				continue

			for child in tag.children:
				if isinstance(child, NavigableString):
					continue
				new_tags.append(child)

			if pred(tag):
				result = on_found(tag)
				if result is SearchAction.CONTINUE:
					continue
				if result is SearchAction.LIMIT:
					break
				if result == SearchAction.STOP:
					return

		current_depth += 1
		if new_tags and current_depth <= max_depth:
			self._search_meta(new_tags, pred, on_found, max_depth, current_depth)

	def pretty_desc(self, tag):
		self.remove_versioning(tag)
		self.remove_headnote(tag)
		self.convert_brs(tag)
		md = self.h2m.convert(str(tag))

		sp = md.split('.\n')
		return md[0:len(sp[0]) + 1] if len(sp) > 1 else md


class HeadersParser(BaseParser):
	def handle(self, id, tag):
		names = self.tag_as_names(tag)
		desc, syntax = self.get_desc_and_syntax(tag)

		self.add(fill_names=names, page='{}#{}'.format(self.page, id), desc=desc, syntax=syntax)

	def go(self):
		self.add_page_entry()

		for tag in self.bs.find_all(HEADER_RE, id=True):
			self.handle(tag.get('id'), tag)


class CommandParser(HeadersParser):
	def add_page_entry(self):
		body = self.bs.find('body')

		header = body.find('h1')
		if header is None:
			return

		names = self.tag_as_names(header)
		desc, syntax = self.get_desc_and_syntax(header)

		self.add(force_names=names, page=self.page, desc=desc, syntax=syntax)


class VariablesParser(BaseParser):
	def go(self):
		for tr in self.bs.find_all('tr'):
			first = True
			names, desc = None, None
			for td in tr.find_all('td'):
				if first:
					first = False
					names = self.tag_as_names(td)
				else:
					desc = self.pretty_desc(td)

			if names is None:
				continue

			_id = tr.get('id')

			if _id is not None:
				names.append(_id)
				page = '{}#{}'.format(self.page, _id)
			else:
				page = None

			self.add(fill_names=names, page=page, desc=desc)


class MethodListParser(BaseParser):
	def go(self):
		self.add_page_entry()

		for tag in self.bs.find_all('div', id=True):
			_id = tag.get('id')
			header = tag.find('h2')
			names = self.tag_as_names(header)

			desc, syntax = self.get_desc_and_syntax(header)

			self.add(force_names=names, page='{}#{}'.format(self.page, _id), desc=desc, syntax=syntax)


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

		contents = self.get_content(tag)

		self.result.add_and_consume(front + contents + back)
