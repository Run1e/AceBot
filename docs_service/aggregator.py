import json
import os

from parsers import Entry, HeadersParser
from tqdm import tqdm


class Aggregator:
    def __init__(self, folder, version) -> None:
        self.folder = folder
        self.version = version
        self.entries = dict()
        self._parsed_files = set()

    def bulk_parse_from_dir(self, path, parser_type, **parser_kwargs):
        return self.bulk_parse(
            [
                parser_type(self.folder, self.version, htm, **parser_kwargs)
                for htm in self._get_htms(path, parser_type)
            ]
        )

    def bulk_parse(self, parsers):
        for parser in tqdm(parsers):
            parser.parse()

            if parser.page not in self.entries:
                # page has not been parsed before, so just plonk parser entries into aggregator entries
                self.entries[parser.page] = parser.entries
            else:
                # page HAS been parsed before, so we need to weave/update entries
                current_entries = self.entries[parser.page]
                for fragment, entry in parser.entries.items():
                    present_entry = current_entries.get(fragment, None)
                    if present_entry is None:
                        current_entries[fragment] = entry
                    else:
                        present_entry.merge(entry)

            self._parsed_files.add((parser.__class__, parser.page))

    def parse_data_index(self, file):
        parser_cache = dict()

        with open(f"{self.folder}/{file}") as f:
            index = json.loads(f.read()[12:-2])
            for indice in tqdm(index):
                name, page, *_ = indice

                if "#" in page:
                    page, fragment = page.split("#")
                else:
                    fragment = None

                if page in parser_cache:
                    parser = parser_cache[page]
                else:
                    parser = HeadersParser(self.folder, self.version, page)
                    parser_cache[page] = parser

                tag = parser.bs.find(True, id=fragment)
                text, syntax, version = parser.tag_parse(tag)

                entry = Entry(
                    name=name,
                    primary_names=parser.name_splitter(name)[1],
                    page=page,
                    content=text or None,
                    fragment=fragment,
                    syntax=syntax,
                    version=version,
                    parents=None,
                    secondary_names=None,
                )

                if page not in self.entries:
                    self.entries[page] = dict()

                current_entry = self.entries[page].get(fragment, None)
                if current_entry is None:
                    self.entries[page][fragment] = entry
                else:
                    current_entry.merge(entry)

    def iter_entries(self):
        for entries in self.entries.values():
            for entry in entries.values():
                yield entry

    def name_map(self):
        mapper = dict()  # name: id

        for entry in self.iter_entries():
            for pname in entry.primary_names:
                if pname not in mapper:
                    mapper[pname] = entry.id

        for entry in self.iter_entries():
            if entry.secondary_names is None:
                continue
            for pname in entry.secondary_names:
                if pname not in mapper:
                    mapper[pname] = entry.id

        return mapper

    def assign_ids(self, start_at):
        _id = start_at
        for entry in self.iter_entries():
            entry.id = _id
            _id += 1

    @property
    def entry_count(self):
        count = 0
        for _ in self.iter_entries():
            count += 1
        return count

    def _get_htms(self, folder, filter_on_type):
        filtered = []
        for file in os.listdir(f"{self.folder}/{folder}"):
            if not file.endswith(".htm"):
                continue

            file = f"{folder}/{file}"

            if (filter_on_type, file) in self._parsed_files:
                continue

            filtered.append(file)

        return filtered

    def printer(self):
        for entry in self.iter_entries():
            print("UUID:", entry.id)
            print("Name:", entry.name)
            print("Primary names:", entry.primary_names)
            print("Secondary names:", entry.secondary_names)
            print("Page:", entry.page)
            print("Fragment:", entry.fragment)
            print("Syntax:", entry.syntax)
            print("Version:", entry.version)
            print("Parents:", entry.parents)
            print()
            print(entry.content)

            print("\n", "-" * 100, "\n")
