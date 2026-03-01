import asyncpg
import json
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
_openai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])


async def _embed(text: str, **_) -> list[float]:
    response = await _openai.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


def _embedding_to_str(embedding: list[float]) -> str:
    return "[" + ",".join(str(x) for x in embedding) + "]"


async def upload_config(
    domain: str,
    url_pattern: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
) -> str:
    """Insert a config row, generate its embedding, and return its id."""
    embed_input = f"{title}. {description}. {' '.join(tags or [])}"
    embedding = await _embed(embed_input)

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO configs (domain, url_pattern, title, description, tags, embedding)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::vector)
            RETURNING id
            """,
            domain,
            url_pattern,
            title,
            description,
            json.dumps(tags) if tags is not None else None,
            _embedding_to_str(embedding),
        )
        return str(row["id"])
    finally:
        await conn.close()


async def get_configs(domain: str | None = None) -> list[dict]:
    """Fetch configs, optionally filtered by domain."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        if domain:
            rows = await conn.fetch(
                "SELECT id, domain, url_pattern, title, description, tags, visit_count, created_at, updated_at "
                "FROM configs WHERE domain = $1 ORDER BY created_at DESC",
                domain,
            )
        else:
            rows = await conn.fetch(
                "SELECT id, domain, url_pattern, title, description, tags, visit_count, created_at, updated_at "
                "FROM configs ORDER BY created_at DESC"
            )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_configs_for_query(query: str, limit: int = 3) -> list[dict]:
    """Semantic search — returns the most relevant configs for a natural language query."""
    embedding = await _embed(query, input_type="search_query")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch(
            """
            SELECT domain, url_pattern, description, visit_count
            FROM configs
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            _embedding_to_str(embedding),
            limit,
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()
