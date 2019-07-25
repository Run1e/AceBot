import os, aiohttp, json, shutil

from utils.docs_parser.handlers import *
from utils.html2markdown import html2markdown

from zipfile import ZipFile
from bs4 import BeautifulSoup

URL = 'https://www.autohotkey.com/docs'
PARSER = 'html.parser'
EXTRACT_TO = 'temp'
DOCS_BASE = f'{EXTRACT_TO}/AutoHotkey_L-Docs-master'
DOCS_FOLDER = f'{DOCS_BASE}/docs'
DOWNLOAD_FILE = f'{EXTRACT_TO}/docs.zip'
DOWNLOAD_LINK = 'https://github.com/Lexikos/AutoHotkey_L-Docs/archive/master.zip'

directory_handlers = dict(
	commands=CommandsHandler,
	misc=BaseHandler,
	objects=BaseHandler
)

file_handlers = {
	'Variables.htm': VariablesHandler,
	'commands/Math.htm': CommandListHandler,
	'commands/GuiControls.htm': CommandListHandler, # contains SB_*() functions
	'commands/ListView.htm': CommandListHandler,
	'commands/TreeView.htm': CommandListHandler,
	'commands/Gui.htm': CommandListHandler,
	'commands/Menu.htm': CommandListHandler
}


customs = (
	(('Symbols', 'Hotkey Modifier Symbols'), 'Hotkeys.htm#Symbols', 'List of Hotkey Modifier Symbols.'),
	(('Simple Arrays',), 'Objects.htm#Usage_Simple_Arrays', 'Overview of simple, indexed arrays.'),
	(('Associative arrays', 'Dictionary'), 'Objects.htm#Usage_Associative_Arrays', 'Overview of associative arrays (key/value).'),
	(('Freeing Objects',), 'Objects.htm#Usage_Freeing_Objects', 'How to free objects from memory.')
)


async def parse_docs(handler, on_update, fetch=True):
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

	# for embedded URLs, they need the URL base
	BaseHandler.url_base = URL
	BaseHandler.file_base = DOCS_FOLDER

	# parse object pages
	await on_update('Building...')
	for dir, handlr in directory_handlers.items():
		for filename in filter(lambda fn: fn.endswith('.htm'), os.listdir(f'{DOCS_FOLDER}/{dir}')):
			fn = f'{dir}/{filename}'
			if fn in file_handlers:
				continue
			await handlr(fn, handler).parse()

	for file, handlr in file_handlers.items():
		await handlr(file, handler).parse()

	# main pages
	for filename in filter(lambda fn: fn.endswith('.htm'), os.listdir(f'{DOCS_FOLDER}')):
		await SimpleHandler(filename, handler).parse()

	# customly added stuff
	for names, page, desc in customs:
		await handler(names, page, desc)

	# parse the index list and add additional names for stuff
	with open(f'{DOCS_FOLDER}/static/source/data_index.js') as f:
		j = json.loads(f.read()[12:-2])
		for line in j:
			name, page, *junk = line

			if '#' in page:
				page_base, offs = page.split('#')
			else:
				page_base = page
				offs = None

			with open(f'{DOCS_FOLDER}/{page_base}') as f:
				bs = BeautifulSoup(f.read(), 'html.parser')

				if offs is None:
					p = bs.find('p')
				else:
					p = bs.find(True, id=offs)

				if p is None:
					desc = None
				else:
					md = html2markdown(str(p), escaper=discord.utils.escape_markdown, url=URL)

					sp = md.split('.\n')
					desc = md[0:len(sp[0]) + 1] if len(sp) > 1 else md

			await handler([name], page, desc)

	await on_update('Build finished successfully.')
