import asyncio

from docs_parser import parse_docs



async def main():
	async def on_update(text):
		print(text)

	async def handler(names, page, desc, syntaxes=None, params=None):
		print(names)
		print(f'page: {page}')
		print(desc)
		print(syntaxes)
		print()
		print()

	await parse_docs(handler, on_update, False)

if __name__ == '__main__':
	asyncio.run(main())