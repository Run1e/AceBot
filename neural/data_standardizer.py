import os
import re
import string

from unidecode import unidecode

from torch_config import CORPUS_DIR


def standardize(s: str):
	# make lowercase
	s = s.lower()

	# remove urls
	s = re.sub(r'^https?:\/\/.*[\r\n]*', '', s, flags=re.MULTILINE)

	# remove diacritics
	s = unidecode(s)

	# remove numbers
	s = re.sub(f'[{string.digits}\.,]', ' ', s)

	# remove punctuation
	s = re.sub(f'[{re.escape(string.punctuation)}]', '', s)

	# condense whitespaces
	s = re.sub(r'\s+', ' ', s)

	return s.lower().strip()


def main():
	for folder, subfolders, files in os.walk(f'{CORPUS_DIR}/raw'):
		if files:
			for i, file in enumerate(files):
				with open(folder + '/' + file, 'r', encoding='utf-8') as f:
					data = f.read()

				new_folder = folder.replace('\\', '/').replace('raw', 'proc')

				if not os.path.isdir(new_folder):
					os.mkdir(new_folder)

				new = standardize(data)

				if not len(new):
					continue

				with open((new_folder + '/' + file).replace('raw', 'proc'), 'w', encoding='utf-8') as f:
					f.write(new)


if __name__ == '__main__':
	main()
