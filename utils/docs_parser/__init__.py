import os
import json
import shutil
import aiohttp
import logging

from zipfile import ZipFile

from utils.docs_parser.handlers import *

DOCS_URL = 'https://www.autohotkey.com/docs/'
EXTRACT_TO = 'data'
DOCS_BASE = f'{EXTRACT_TO}/AutoHotkey_L-Docs-master'
DOCS_FOLDER = f'{DOCS_BASE}/docs'
DOWNLOAD_FILE = f'{EXTRACT_TO}/docs.zip'
DOWNLOAD_LINK = 'https://github.com/Lexikos/AutoHotkey_L-Docs/archive/master.zip'

log = logging.getLogger(__name__)


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
		if entry.get('desc', None) is None:
			return

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

		if entry['page'] is None:
			similar_entry = None
		else:
			similar_entry = self.get_entry_by_page(entry['page'])

		if similar_entry is None:
			self.entries.append(entry)
		else:
			for name in filter(lambda name: name not in similar_entry['names'], entry['names']):
				similar_entry['names'].append(name)


async def parse_docs(on_update, fetch=True):
	if fetch:
		await on_update('Downloading...')

		# delete old stuff
		try:
			os.remove(DOWNLOAD_FILE)
		except FileNotFoundError:
			pass

		shutil.rmtree(DOCS_BASE, ignore_errors=True)

		# fetch docs package
		async with aiohttp.ClientSession() as session:
			async with session.get(DOWNLOAD_LINK) as resp:
				if resp.status != 200:
					await on_update('download failed.')
					return

				with open(DOWNLOAD_FILE, 'wb') as f:
					f.write(await resp.read())

		# and extract it
		zip_ref = ZipFile(DOWNLOAD_FILE, 'r')
		zip_ref.extractall(EXTRACT_TO)
		zip_ref.close()

	await on_update('Building...')

	aggregator = DocsAggregator()
	BaseParser.DOCS_URL = DOCS_URL
	BaseParser.DOCS_FOLDER = DOCS_FOLDER

	parsers = (
		HeadersParser('commands/Math.htm'),
		HeadersParser('commands/ListView.htm'),
		HeadersParser('commands/TreeView.htm'),
		HeadersParser('commands/Gui.htm', prefix='Gui: '),
		HeadersParser('commands/Menu.htm', prefix='Menu: '),
		GuiControlParser('commands/GuiControls.htm', postfix=' Control'),
		HeadersParser('objects/Functor.htm'),
		MethodListParser('objects/File.htm'),
		MethodListParser('objects/Func.htm'),
		MethodListParser('objects/Object.htm'),
		EnumeratorParser('objects/Enumerator.htm'),
		HeadersParser('KeyList.htm'),
		# VariablesParser('KeyList.htm', prefix='Key: '),
		HeadersParser('Functions.htm'),
		VariablesParser('Functions.htm'),
		HeadersParser('Hotkeys.htm'),
		VariablesParser('Hotkeys.htm'),
		HeadersParser('Variables.htm', ignores=['Loop']),
		VariablesParser('Variables.htm'),
		HeadersParser('Objects.htm'),
		HeadersParser('Program.htm'),
		HeadersParser('Scripts.htm'),
		HeadersParser('Concepts.htm'),
		HeadersParser('HotkeyFeatures.htm'),
		HeadersParser('Language.htm'),
		HeadersParser('Tutorial.htm'),
		HeadersParser('AHKL_DBGPClients.htm'),
		HeadersParser('AHKL_Features.htm'),
		VariablesParser('AHKL_Features.htm'),
	)

	for file in sorted(os.listdir('{}/commands'.format(DOCS_FOLDER))):
		if file.endswith('.htm'):
			for entry in CommandParser('commands/{}'.format(file)).run():
				aggregator.add_entry(entry)

	for parser in parsers:
		for entry in parser.run():
			aggregator.add_entry(entry)

	for file in sorted(os.listdir('{}/misc'.format(DOCS_FOLDER))):
		if file.endswith('.htm'):
			for entry in HeadersParser('misc/{}'.format(file)).run():
				aggregator.add_entry(entry)

	parsers[0].page = DOCS_URL

	with open(f'{DOCS_FOLDER}/static/source/data_index.js') as f:
		j = json.loads(f.read()[12:-2])
		for line in j:
			name, page, *junk = line

			if not aggregator.name_check(name):
				continue

			if '#' in page:
				page_base, offs = page.split('#')
			else:
				page_base, offs = page, None

			with open(f'{DOCS_FOLDER}/{page_base}') as f:
				bs = BeautifulSoup(f.read(), 'html.parser')

				p = bs.find('p') if offs is None else bs.find(True, id=offs)
				desc = None if p is None else parsers[0].pretty_desc(p)

			entry = dict(names=parsers[0]._string_as_names(name), page=page, desc=desc)
			aggregator.add_entry(entry)

	await on_update('List built. Total names: {} Unique entries: {}\n'.format(
		sum(len(entry['names']) for entry in aggregator.entries),
		len(aggregator.entries)
	))

	return aggregator
