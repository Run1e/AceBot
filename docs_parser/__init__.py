import os, aiohttp, zipfile, json

from docs_parser.handlers import *

from bs4 import BeautifulSoup

url = 'https://www.autohotkey.com/docs'
parser = 'html.parser'
docs_base = 'temp/AutoHotkey_L-Docs-master/docs'
download_file = 'temp/docs.zip'
download_link = 'https://github.com/Lexikos/AutoHotkey_L-Docs/archive/master.zip'

directory_handlers = dict(
	commands=CommandsHandler,
	misc=MiscHandler,
	objects=ObjectHandler
)

file_handlers = {
	'Variables.htm': VariablesHandler,
	'commands/Math.htm': CommandListHandler,
	'commands/ListView.htm': CommandListHandler,
	'commands/TreeView.htm': CommandListHandler
}

customs = (
	(('FAQ',), 'FAQ.htm', 'Some frequently asked questions about the language.'),
	(('Tutorial', 'Tutorial by tidbit'), 'Tutorial.htm', 'Learn the basics with tidbit!'),
	(('Hotkeys',), 'Hotkeys.htm', 'Hotkeys, modifiers symbols and examples.'),
	(('Symbols', 'Hotkey Modifier Symbols'), 'Hotkeys.htm#Symbols', 'List of Hotkey Modifier Symbols.'),
	(('Hotstrings',), 'Hotstrings.htm', 'Hotstring how-to.'),
	(('Key List',), 'KeyList.htm', 'List of keyboard, mouse and joystick buttons/keys.'),
	(('Arrays', 'Simple Arrays'), 'Objects.htm#Usage_Simple_Arrays', 'Overview of simple, indexed arrays.'),
	(('Associative arrays', 'Dictionary'), 'Objects.htm#Usage_Associative_Arrays', 'Overview of associative arrays (key/value).'),
	(('Freeing Objects',), 'Objects.htm#Usage_Freeing_Objects', 'How to free objects from memory.')
)

async def parse_docs(handler, on_update, fetch=True):
	if fetch:
		await on_update('downloading zip...')

		async with aiohttp.ClientSession() as session:
			async with session.get(download_link) as resp:
				if resp.status != 200:
					await on_update('download failed.')
					return

				with open(download_file, 'wb') as f:
					f.write(await resp.read())

		await on_update('unzipping...')

		zip_ref = zipfile.ZipFile(download_file, 'r')
		zip_ref.extractall('temp')
		zip_ref.close()

	# for embedded URLs, they need the URL base
	BaseHandler.url = url

	# parse object pages
	await on_update('parsing directories...')
	for dir, handlr in directory_handlers.items():
		for filename in filter(lambda fn: fn.endswith('.htm'), os.listdir(f'{docs_base}/{dir}')):
			fn = f'{dir}/{filename}'
			if fn in file_handlers:
				continue
			with open(f'{docs_base}/{fn}', 'r') as f:
				await handlr(BeautifulSoup(f.read(), parser), fn, handler).parse()

	await on_update('parsing single files...')
	for file, handlr in file_handlers.items():
		with open(f'{docs_base}/{file}', 'r') as f:
			await handlr(BeautifulSoup(f.read(), parser), file, handler).parse()

	# customly added stuff
	await on_update('adding custom stuff...')
	for names, page, desc in customs:
		await handler(names, page, desc)

	# parse the index list and add additional names for stuff
	await on_update('parsing index list for additional name matches...')
	with open(f'{docs_base}/static/source/data_index.js') as f:
		j = json.loads(f.read()[12:-2])
		for line in j:
			name, page, *junk = line
			await handler([name], page)

	await on_update('finished!')
