import asyncio
import os

import asyncpg
from aggregator import Aggregator
from bs4 import BeautifulSoup
from parser_instances.v1 import default_command_kwargs, default_misc_kwargs
from parser_instances.v1 import get as v1_get
from parsers import HeadersParser

import config


async def main():
    if False:
        for i, file in enumerate(sorted(os.listdir("docs/lib"))):
            if i < 98:
                continue

            found = False
            for parser in parsers:
                if parser.page == f"lib/{file}":
                    found = True
                    break

            if found:
                continue

            bs = BeautifulSoup(open(f"docs/lib/{file}", "r").read(), "lxml")
            print(file)
            h = []
            for tag in bs.find_all(re.compile(r"^h\d$")):
                h.append(tag.name)

            print(h)

            print()
            print("-" * 200)
            print()


async def store(pool: asyncpg.Pool, agg: Aggregator, version: int, id_start_at=1):
    print("storing version", version, "starting at id", id_start_at)

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
            entry.content,
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


async def build_v1_aggregator(folder) -> Aggregator:
    print("parsing v1 docs")

    agg = Aggregator(folder)

    agg.bulk_parse(v1_get(folder))
    agg.bulk_parse_from_dir("lib", parser_type=HeadersParser, **default_command_kwargs)
    agg.bulk_parse_from_dir("misc", parser_type=HeadersParser, **default_misc_kwargs)
    agg.parse_data_index("static/source/data_index.js")

    print(agg.entry_count, "entries")
    print(len(agg.name_map()), "names")

    return agg


async def main():
    db = await asyncpg.create_pool(config.DB_BIND)
    await db.execute("TRUNCATE docs_name, docs_entry RESTART IDENTITY")

    agg = await build_v1_aggregator("docs")
    await store(db, agg, 1)

    start_at = agg.entry_count + 1

    await db.close()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
