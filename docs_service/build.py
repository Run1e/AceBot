import asyncio
import os
import re
import shutil
from zipfile import ZipFile

import aiohttp
import asyncpg
from aggregator import Aggregator
from bs4 import BeautifulSoup
from parser_instances.common import command, default
from parser_instances.v1 import get as v1_get
from parser_instances.v2 import get as v2_get
from parsers import HeadersParser

import config


async def view_h(parsers, base, path):
    folder = base
    if path:
        folder += f"/{path}"
    for i, file in enumerate(sorted(os.listdir(folder))):
        if not file.endswith(".htm"):
            continue

        ff = f"{folder}/{file}"

        found = False
        for parser in parsers:
            parser_doink = f"{parser.base}/{parser.page}"
            if parser_doink == ff:
                found = True
                break

        if found:
            continue

        bs = BeautifulSoup(open(ff, "r").read(), "lxml")
        h = []
        a = set()
        for tag in bs.find_all(re.compile(r"^h\d$")):
            h.append(tag.name)
        if bs.find("h3", id="Methods") or bs.find("h3", id="Properties"):
            a.add("object")
        if bs.find("h3", id="SubCommands"):
            a.add("subcommands")

        if a:
            print(file, a)
            print(h)


async def store(pool: asyncpg.Pool, agg: Aggregator, version: int, id_start_at=1):
    print("storing version", version, "starting at id", id_start_at)
    print(agg.entry_count, "entries")
    print(len(agg.name_map()), "names")

    entry_sql = (
        "INSERT INTO docs_entry (id, v, name, page, fragment, content, syntax, version, parents) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"
    )

    name_sql = "INSERT INTO docs_name (v, docs_id, name) VALUES ($1, $2, $3)"

    agg.assign_ids(id_start_at)

    ent = [
        (
            entry.id,
            version,
            entry.name,
            entry.page,
            entry.fragment,
            entry.content if entry.content else None,
            entry.syntax,
            entry.version,
            [e.id for e in entry.parents or []],
        )
        for entry in agg.iter_entries()
    ]

    names = [(version, _id, name) for name, _id in agg.name_map().items()]

    async with pool.acquire() as conn:
        conn: asyncpg.Connection
        async with conn.transaction():
            await conn.executemany(entry_sql, ent)
            await conn.executemany(name_sql, names)

    print("finished storing version", version)


async def downloader(url, download_to, extract_to):
    print("downloading", url)

    # delete old stuff
    try:
        os.remove(download_to)
    except FileNotFoundError:
        pass

    shutil.rmtree(extract_to, ignore_errors=True)

    # fetch docs package
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise ValueError("http returned:", resp.status)

            with open(download_to, "wb") as f:
                f.write(await resp.read())

    print("extracting to ", extract_to)

    # and extract it
    zip_ref = ZipFile(download_to, "r")
    zip_ref.extractall(extract_to)
    zip_ref.close()


async def build_v1_aggregator(folder, download=False) -> Aggregator:
    if download:
        await downloader(
            url="https://github.com/AutoHotkey/AutoHotkeyDocs/archive/v1.zip",
            download_to="docs_v1.zip",
            extract_to=folder,
        )

    print("parsing v1 docs")

    folder += "/AutoHotkeyDocs-1/docs"

    agg = Aggregator(folder=folder, version=1)

    agg.bulk_parse(v1_get(folder))
    agg.bulk_parse_from_dir("lib", parser_type=HeadersParser, **command)
    agg.bulk_parse_from_dir("misc", parser_type=HeadersParser, **default())
    agg.parse_data_index("static/source/data_index.js")

    return agg


async def build_v2_aggregator(folder, download=False) -> Aggregator:
    if download:
        await downloader(
            url="https://github.com/AutoHotkey/AutoHotkeyDocs/archive/v2.zip",
            download_to="docs_v2.zip",
            extract_to=folder,
        )

    print("parsing v2 docs")

    folder += "/AutoHotkeyDocs-2/docs"

    agg = Aggregator(folder=folder, version=2)

    agg.bulk_parse(v2_get(folder))
    agg.bulk_parse_from_dir("lib", parser_type=HeadersParser, **command)
    agg.bulk_parse_from_dir("misc", parser_type=HeadersParser, **default())
    agg.parse_data_index("static/source/data_index.js")

    return agg


async def main():
    db = await asyncpg.create_pool(config.DB_BIND)
    await db.execute("TRUNCATE docs_name, docs_entry, docs_syntax RESTART IDENTITY")

    agg = await build_v1_aggregator("docs_v1", download=True)
    await store(db, agg, 1)
    start_at = agg.entry_count + 1

    print()

    agg = await build_v2_aggregator("docs_v2", download=True)
    await store(db, agg, 2, id_start_at=start_at)

    await db.close()

    print("done")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
    # loop.run_forever()
