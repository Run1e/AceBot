from bs4 import BeautifulSoup
from urllib.parse import urlparse

from pprint import pprint

def google_parse(text):
	soup = BeautifulSoup(text, 'lxml')
	
	g = soup.find(class_='g')
	
	if g is None:
		return None
	
	title = g.h3.string
	link = g.a['href']
	desc = g.find(class_='st')
	
	return title, link, str(desc.text), urlparse(link).netloc