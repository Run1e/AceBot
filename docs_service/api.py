from collections import defaultdict
from random import choices
import re

import asyncpg
from rapidfuzz import fuzz, process
from sanic import Blueprint, Request, Sanic
from sanic.response import HTTPResponse, json

import config

app = Sanic("ahkdocs_api")

api = Blueprint("api", url_prefix="/api")


meaning_scalar = lambda v: 1 / ((v * 0.5) ** 2 + 1)


def processor(s):
    s = s.strip().lower()
    return re.sub(r"(\(|\))", "", s)


def docs_search(names, query, k):
    query = query.strip()

    if not query:
        return choices(names, k=k)

    word_scores = []

    splitters = [query]
    splitters.extend(query.split(" "))
    scores = defaultdict(float)

    for i, word in enumerate(splitters):
        word_scores = process.extract(
            query=word,
            choices=names,
            scorer=fuzz.WRatio,
            processor=processor,
            limit=100,
        )

        for name, score, _ in word_scores:
            scores[name] += score * meaning_scalar(i)

    return list(name for name, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True))[
        :k
    ]


def entry_to_dict(row):
    return dict(
        id=row.get("id"),
        v=row.get("v"),
        name=row.get("name"),
        page=row.get("page"),
        fragment=row.get("fragment"),
        content=row.get("content"),
        syntax=row.get("syntax"),
        version=row.get("version"),
    )


async def get_entry(conn: asyncpg.Connection, docs_id: int, lineage=True, search_match=None):
    row = await conn.fetchrow("SELECT * FROM docs_entry WHERE id=$1", docs_id)

    o = entry_to_dict(row)

    if lineage:
        parents = []
        children = []

        for parent_id in row.get("parents"):
            if parent_id is None:  # shouldn't happen
                continue
            parents.append(await get_entry(conn, parent_id, lineage=False))

        rows = await conn.fetch(
            "SELECT * FROM docs_entry WHERE parents[array_upper(parents, 1)] = $1",
            docs_id,
        )
        for row in rows:
            children.append(entry_to_dict(row))

        o["parents"] = parents
        o["children"] = children
        o["search_match"] = search_match

    return o


@api.post("/search")
async def search(request: Request):
    data = request.json

    if data is None:
        return HTTPResponse(status=400)

    q = data.get("q", None)
    v = data.get("v", None)

    if q is None or v is None:
        return HTTPResponse(status=400)

    if not isinstance(q, str) or not isinstance(v, int):
        return HTTPResponse(status=400)

    names = app.ctx.names[v]

    res = docs_search(names, q, k=5)
    return json(res)


@api.post("/entry")
async def entry(request: Request):
    data = request.json

    if data is None:
        return HTTPResponse(status=400)

    q = data.get("q", None)
    v = data.get("v", None)

    if q is None or v is None:
        return HTTPResponse(status=400)

    if not isinstance(q, str) or not isinstance(v, int):
        return HTTPResponse(status=400)

    names = app.ctx.names[v]

    res = docs_search(names, q, k=1)[0]
    docs_id = app.ctx.id_map[v][res]

    async with app.ctx.pool.acquire() as conn:
        conn: asyncpg.Connection
        async with conn.transaction():
            return json(await get_entry(conn, docs_id, lineage=True, search_match=res))


@app.signal("server.init.before")
async def setup(app, loop):
    pool = await asyncpg.create_pool(config.DB_BIND)

    async with pool.acquire() as conn:
        conn: asyncpg.Connection
        async with conn.transaction():
            res = await conn.fetch("SELECT * FROM docs_name")
            id_map = {v: {} for v in (1, 2)}
            names = {v: [] for v in (1, 2)}

            for row in res:
                v = row.get("v")
                docs_id = row.get("docs_id")
                name = row.get("name")
                id_map[v][name] = docs_id
                names[v].append(name)

    app.ctx.names = names
    app.ctx.id_map = id_map
    app.ctx.pool = pool


app.blueprint(api)
app.run("0.0.0.0", 80)
