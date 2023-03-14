import re
from itertools import chain
from typing import List
from uuid import uuid4

from bs4 import BeautifulSoup, NavigableString, Tag
from markdownify import MarkdownConverter

DOCS_URL = "https://www.autohotkey.com/docs/v1/"
ANY_HEADER_RE = re.compile(r"^h\d$")
BIG_HEADER_RE = re.compile(r"^h[1-3]$")
BULLET = "•"


class Entry:
    def __init__(
        self,
        name,
        primary_names,
        page,
        content,
        fragment=None,
        syntax=None,
        version=None,
        parents=None,
        secondary_names=None,
    ):
        self.id = None
        self.name = name
        self.primary_names = primary_names
        self.page = page
        self.fragment = fragment
        self.content = content
        self.syntax = syntax
        self.version = version
        self.parents = parents
        self.secondary_names = secondary_names

    def merge(self, other):
        or_fields = ("content", "syntax", "version")
        for field in or_fields:
            setattr(self, field, getattr(self, field) or getattr(other, field))

        if self.secondary_names is None:
            self.secondary_names = []

        self.secondary_names.extend(other.primary_names)


class DocsMarkdownConverter(MarkdownConverter):
    def convert_span(self, el: Tag, text, convert_as_inline):
        classes = el.get("class", None)
        if classes is None:
            return text

        if "optional" in classes:
            return f"[{text}]"

        if "ver" in classes:
            self.version = text

        return text

    def convert_code(self, el, text, convert_as_inline):
        return f"`{text}`"


def md(soup, **converter_kwargs):
    converter = DocsMarkdownConverter(convert=["span", "code"], **converter_kwargs)
    converter.version = None
    text = converter.convert_soup(soup).strip()
    return text, converter


class Parser:
    def __init__(self, base, page) -> None:
        self.base = base
        self.page = page
        self.parser = "lxml"

        self.entries = dict()

        with open(f"{self.base}/{self.page}", "r") as f:
            self.bs = BeautifulSoup(f.read(), self.parser)

    def add_entry(self, entry: Entry):
        self.entries[entry.fragment] = entry

    def parse(self):
        raise NotImplementedError("Must be implemented by subclass")

    def tag_to_str(self, tag: Tag):
        def to_str(tag):
            if isinstance(tag, NavigableString):
                return str(tag)
            elif tag.name == "br":
                return "\n"

            content = ""
            for child in tag.children:
                content += to_str(child)

            return content

        return to_str(tag).strip() or None

    def strip_versioning(self, tag: Tag):
        found_tags = tag.find_all("span", class_="ver")
        if not found_tags:
            return None

        ver = self.tag_to_str(found_tags[0])

        for found_tag in found_tags:
            found_tag.decompose()

        return ver

    def tag_parse(self, parent_tag: Tag):
        markup = "<div>"
        found_p = False
        syntax = None
        tag: Tag = parent_tag

        while tag := tag.next_sibling:
            if isinstance(tag, NavigableString):
                markup += tag
                continue

            elif tag.name == "p":
                if not found_p:
                    markup += str(tag)
                    found_p = True
                else:
                    break

            elif tag.name == "pre":
                _classes = tag.get("class", [])

                if "Syntax" in _classes:
                    syntax, _ = md(tag, escape_underscores=False)

                break

            else:
                break

        text, conv = md(BeautifulSoup(markup, self.parser))
        return text, syntax, conv.version

    def name_splitter(self, orig_name):
        names = [orig_name]
        splits = [" / ", "\n"]

        temp = []
        for name in names:
            for split in splits:
                if split in name:
                    temp.extend(name.split(split))
                    break
            else:
                temp.append(name)

        temp = [name.strip() for name in temp if name.strip()]

        return orig_name, temp


class HeadersParser(Parser):
    def __init__(
        self,
        base,
        page,
        prefix_mapper=None,
        basic_name_check=lambda h, t, p: True,
        ignore=lambda h, t, p: False,
    ) -> None:
        self.prefix_mapper: list = prefix_mapper
        self.basic_name_check = basic_name_check
        self.ignore = ignore
        super().__init__(base, page)

    def level_from_header_tag(self, tag: Tag):
        return int(tag.name[1])

    def names_from_header(self, tag: Tag, parents: list):
        orig_name, names = self.name_splitter(self.tag_to_str(tag))

        return orig_name, list(
            chain(*[self._names_from_header(name, tag, parents) for name in names])
        )

    def _names_from_header(self, text: str, tag: Tag, parents: list):
        h_level = self.level_from_header_tag(tag)
        parent_ids = [p.fragment or p.name for p in parents if p is not None]
        names = []

        try:
            add_name = self.basic_name_check(h_level, tag, parent_ids)
        except IndexError:
            add_name = True

        if add_name:
            names.append(text)

        def do_action(action):
            if isinstance(action, int):
                try:
                    parent = parents[action]
                    parent_name = parent.primary_names[0]
                    if text.startswith(parent_name):
                        new_text = text[len(parent_name) :].strip()
                    else:
                        new_text = text
                    names.append(f"{parent.primary_names[0]} {BULLET} {new_text}")
                except IndexError:
                    pass
            elif isinstance(action, str):
                names.append(action.format(text))
            elif callable(action):
                names.append(action(text))

        if self.prefix_mapper is not None:
            for check, action in self.prefix_mapper:
                if isinstance(check, int):
                    if h_level == check:
                        do_action(action)
                        break
                elif callable(check):
                    try:
                        if check(h_level, tag, parent_ids):
                            do_action(action)
                            break
                    except:
                        pass

        return names

    def process_tag(self, tag: Tag, parents: list):
        header_version = self.strip_versioning(tag)
        name, primary_names = self.names_from_header(tag, parents)
        text, syntax, parsed_version = self.tag_parse(tag)
        version = header_version or parsed_version

        fragment = tag.get("id", None)

        # fix for methods in object-like pages, since their method h3 tags
        # do not have an id attr, but their previous_sibling div has, we
        # just manually check for that instead
        # really we should not be using a HeadersParser, and rather
        # use something that finds methods by finding divs with ids
        previous = tag.previous_element
        if previous.name == "div" and "methodShort" in previous.get("class", []):
            fragment = previous.get("id", None)

        entry = Entry(
            name=name,
            primary_names=primary_names,
            page=self.page,
            content=text,
            fragment=fragment,
            syntax=syntax,
            version=version,
            parents=parents[1:],
            secondary_names=None,
        )

        self.add_entry(entry)
        return entry

    def parse(self):
        parents = [None] * 10

        for tag in self.bs.find_all(ANY_HEADER_RE):
            ids = tag.get("id", None)

            if ids is not None and "toc" in ids:
                continue

            h_level = self.level_from_header_tag(tag)
            tag_parents = [e for e in parents[:h_level]]

            try:
                ignore = self.ignore(h_level, tag, tag_parents)
            except:
                ignore = False

            if ignore:
                continue

            entry = self.process_tag(tag, tag_parents)

            if entry is not None:
                parents[h_level] = entry


class TableParser(Parser):
    def parse(self):
        for tr in self.bs.find_all("tr", id=True):
            first = True
            for td in tr.find_all("td"):
                if first:
                    first = False
                    version = self.strip_versioning(td)
                    orig_name, names = self.name_splitter(self.tag_to_str(td))
                else:
                    desc, conv = md(td)

            fragment = tr.get("id")

            entry = Entry(
                name=orig_name,
                primary_names=names,
                page=self.page,
                content=desc,
                fragment=fragment,
                version=version or conv.version,
            )

            self.add_entry(entry)
