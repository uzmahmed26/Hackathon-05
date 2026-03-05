"""
Product Docs Indexer
--------------------
Reads context/product-docs.md, chunks it into FAQ sections,
generates OpenAI text-embedding-3-small embeddings (VECTOR 1536),
and upserts them into the knowledge_base table.

Usage:
    python scripts/index_product_docs.py [--docs-path PATH] [--dsn DSN]

Environment variables (fallbacks):
    DATABASE_URL     PostgreSQL DSN
    OPENAI_API_KEY   OpenAI API key
"""

import argparse
import asyncio
import logging
import os
import re
import sys
from pathlib import Path
from typing import Iterator

import asyncpg
import openai
from dotenv import load_dotenv

# Load .env from project root before reading any env vars
load_dotenv(Path(__file__).parent.parent / ".env")

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

DOCS_PATH = Path(__file__).parent.parent / "context" / "product-docs.md"
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536-dim output
EMBEDDING_DIM = 1536
CHUNK_OVERLAP_LINES = 1  # carry last line of previous chunk into next

# ── Chunking ───────────────────────────────────────────────────────────────────


def _detect_category(heading: str) -> str:
    """Map a Markdown ### heading to a category slug."""
    h = heading.lower()
    # Check troubleshooting first — some headings mention "account" but are really troubleshoot
    if any(k in h for k in ("troubleshoot", "can't log", "can not log", "aren't working",
                             "not working", "not display", "accidentally delet",
                             "isn't receiving", "saving")):
        return "troubleshooting"
    if any(k in h for k in ("pric", "billing", "plan", "discount")):
        return "pricing"
    if any(k in h for k in ("feature", "task", "time", "report", "gantt", "workflow",
                             "file attach", "integrat", "recurring", "mobile")):
        return "features"
    if any(k in h for k in ("get started", "create a new account", "free trial", "invite",
                             "import", "first project")):
        return "getting_started"
    return "general"


def chunk_markdown(text: str) -> Iterator[dict]:
    """
    Yield chunks, one per ### FAQ entry.
    Each chunk dict has: title, content, category.
    Falls back to splitting on ## sections if no ### found.
    """
    # Split on "### N." headings (the product-docs format)
    parts = re.split(r"(?=^###\s)", text, flags=re.MULTILINE)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        lines = part.splitlines()
        heading_line = lines[0].lstrip("#").strip()
        body = "\n".join(lines[1:]).strip()

        if not body:
            continue

        category = _detect_category(heading_line)
        yield {
            "title": heading_line,
            "content": body,
            "category": category,
        }


# ── Embeddings ─────────────────────────────────────────────────────────────────


async def embed_texts(client: openai.AsyncOpenAI, texts: list[str]) -> list[list[float]]:
    """Generate embeddings in batches of up to 100."""
    all_vectors: list[list[float]] = []
    batch_size = 100

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = await client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        all_vectors.extend([item.embedding for item in response.data])

    return all_vectors


# ── Database ───────────────────────────────────────────────────────────────────


async def upsert_chunks(
    conn: asyncpg.Connection,
    chunks: list[dict],
    vectors: list[list[float]],
) -> int:
    """
    Upsert knowledge_base rows.
    Uses ON CONFLICT on title to avoid duplicates on re-runs.
    Returns number of rows inserted/updated.
    """
    count = 0
    for chunk, vector in zip(chunks, vectors):
        if vector is not None:
            vec_str = "[" + ",".join(str(v) for v in vector) + "]"
            await conn.execute(
                """
                INSERT INTO knowledge_base (title, content, category, embedding)
                VALUES ($1, $2, $3, $4::vector)
                ON CONFLICT (title) DO UPDATE
                    SET content   = EXCLUDED.content,
                        category  = EXCLUDED.category,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                """,
                chunk["title"],
                chunk["content"],
                chunk["category"],
                vec_str,
            )
        else:
            await conn.execute(
                """
                INSERT INTO knowledge_base (title, content, category)
                VALUES ($1, $2, $3)
                ON CONFLICT (title) DO UPDATE
                    SET content  = EXCLUDED.content,
                        category = EXCLUDED.category,
                        updated_at = NOW()
                """,
                chunk["title"],
                chunk["content"],
                chunk["category"],
            )
        count += 1
    return count


# ── Schema guard ───────────────────────────────────────────────────────────────


async def ensure_unique_title_index(conn: asyncpg.Connection) -> None:
    """Add a unique index on knowledge_base.title if it doesn't exist."""
    await conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_base_title
            ON knowledge_base (title);
        """
    )


# ── Main ───────────────────────────────────────────────────────────────────────


async def run(docs_path: Path, dsn: str, no_embeddings: bool = False) -> None:
    # 1. Read source markdown
    if not docs_path.exists():
        logger.error(f"Docs file not found: {docs_path}")
        sys.exit(1)

    text = docs_path.read_text(encoding="utf-8")
    chunks = list(chunk_markdown(text))
    logger.info(f"Parsed {len(chunks)} chunks from {docs_path.name}")

    if not chunks:
        logger.error("No chunks extracted — check the markdown format")
        sys.exit(1)

    # 2. Generate embeddings (skip if --no-embeddings or no API key)
    if no_embeddings:
        logger.info("Skipping embeddings (--no-embeddings). Keyword search will be used.")
        vectors = [None] * len(chunks)
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY environment variable not set")
            sys.exit(1)

        oai = openai.AsyncOpenAI(api_key=api_key)
        texts = [f"{c['title']}\n\n{c['content']}" for c in chunks]
        logger.info(f"Generating {len(texts)} embeddings via {EMBEDDING_MODEL} ...")
        vectors = await embed_texts(oai, texts)
        logger.info("Embeddings generated")

    # 3. Upsert into DB
    conn = await asyncpg.connect(dsn)
    try:
        await ensure_unique_title_index(conn)
        count = await upsert_chunks(conn, chunks, vectors)
        logger.info(f"Upserted {count} knowledge_base rows successfully")
    finally:
        await conn.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Index product-docs.md into pgvector knowledge base")
    parser.add_argument(
        "--docs-path",
        type=Path,
        default=DOCS_PATH,
        help="Path to product-docs.md",
    )
    parser.add_argument(
        "--dsn",
        default=os.getenv(
            "DATABASE_URL",
            "postgresql://fte_user:fte_password@localhost:5432/fte_db",
        ),
        help="PostgreSQL DSN",
    )
    parser.add_argument(
        "--no-embeddings",
        action="store_true",
        help="Skip OpenAI embedding generation; use keyword search only",
    )
    args = parser.parse_args()

    asyncio.run(run(args.docs_path, args.dsn, no_embeddings=args.no_embeddings))


if __name__ == "__main__":
    main()
