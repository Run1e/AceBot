import discord
import json
from fuzzywuzzy import fuzz, process

with open('cogs/autohotkey/Docs.json', 'r') as f:
	docs_assoc = json.loads(f.read())
	docs = []
	for x in docs_assoc:
		docs.append(x)

def docs_search(search_terms):
	embed = discord.Embed(color=0x78A064)
	md_trans = str.maketrans({c: '\\'+c for c in '\\*#/()[]<>'})
	search_terms = search_terms.splitlines()

	# Finds a documentation page with fuzzy search
	def find_page(search_term):
		# Simple check
		for page_name in docs:
			if (page_name.lower().startswith(search_term.lower() + ' ')
						or search_term.lower() == page_name.lower()):
				return page_name

		# String matching check
		matches = process.extract(
			search_term,
			docs,
			scorer=fuzz.partial_ratio,
			limit=999999
		)

		for match, score in matches:
			if (search_term.upper() == ''.join(filter(str.isupper, match))
						or match.lower().startswith(search_term.lower())):
				return match

		return matches[0][0]

	# Find one page and put it in a normal embed
	if len(search_terms) == 1:
		page_name = find_page(search_terms[0])
		page = docs_assoc[page_name]

		if 'syntax' in page:
			if page['syntax'].find('\n'):
				page['syntax'] = page['syntax'].split('\n')[0]

		embed.title = page.get('syntax', page_name)
		embed.description = page.get('desc', '')

		if 'dir' in page:
			embed.url = 'https://autohotkey.com/docs/' + page['dir']

		return embed

	# Find multiple pages and put them in embed fields
	seen_pages = set()

	for search_term in search_terms:
		page_name = find_page(search_term)

		# Filter for unique pages
		if page_name in seen_pages:
			continue

		seen_pages.add(page_name)

		# Add the page as a field in the embed
		page = docs_assoc[page_name]

		if 'syntax' in page:
			if page['syntax'].find('\n'):
				page['syntax'] = page['syntax'].split('\n')[0]

		value = page.get('desc', 'Link').translate(md_trans) if 'dir' not in page else '{0}\n[{1}](https://autohotkey.com/docs/{2})'.format(page.get('desc', 'Link').translate(md_trans), 'Documentation', page['dir'].translate(md_trans))

		embed.add_field(name=page.get('syntax', page_name), value=value)

	embed.title = None
	return embed