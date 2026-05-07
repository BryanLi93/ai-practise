"""端到端测试 ingest 服务。运行:python -m scripts.test_ingest"""
import asyncio
import logging
from sqlalchemy import select, func

from app.db import AsyncSessionLocal
from app.services.ingest import ingest_text_file
from app.models import Document, Chunk

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def main():
    sample_text = """
# Python 简介

Python 是一种解释型、面向对象的高级编程语言。

## 设计哲学

Python 的设计哲学强调代码可读性和简洁的语法。
它支持多种编程范式,包括面向对象、命令式、函数式编程。

## 应用领域

Python 被广泛应用于 Web 开发、数据分析、人工智能、自动化运维等领域。
著名的框架包括 Django、Flask、FastAPI 等。
"""

    async with AsyncSessionLocal() as db:
        # 入库
        result = await ingest_text_file(
            db,
            filename="python_intro.md",
            content_type="text/markdown",
            content=sample_text,
            byte_size=len(sample_text.encode("utf-8")),
        )

        print(f"\n✓ Created document id={result.document.id}")
        print(f"  filename={result.document.filename}")
        print(f"  chunks={result.chunk_count}")

        # 验证查询
        doc_count = await db.scalar(select(func.count(Document.id)))
        chunk_count = await db.scalar(select(func.count(Chunk.id)))
        print(f"\nDB state: {doc_count} documents, {chunk_count} chunks total")

        # 抽查一个 chunk
        first_chunk = await db.scalar(
            select(Chunk).where(Chunk.document_id == result.document.id).limit(1)
        )
        if first_chunk:
            embedding_list = first_chunk.embedding.to_list()
            print(f"\nFirst chunk:")
            print(f"  index={first_chunk.chunk_index}")
            print(f"  tokens={first_chunk.token_count}")
            print(f"  embedding dim={len(embedding_list)}")
            print(f"  embedding preview={embedding_list[:5]}")
            print(f"  content preview: {first_chunk.content[:50]}...")


if __name__ == "__main__":
    asyncio.run(main())