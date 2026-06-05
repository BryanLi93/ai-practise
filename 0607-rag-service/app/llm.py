"""
OpenAI 兼容客户端(指向中转站 base_url),chat 和 embedding 共用一个。

chat(查询改写 / 答案生成)和 embedding(text-embedding-3-*)都走这个中转站,
同一个 base_url + key,所以共享一个 AsyncOpenAI 单例。

放在独立模块而非 chat.py:retrieval.py / embedding.py 都要用,而 chat.py 又 import
retrieval,放 chat.py 会形成循环 import。这里只依赖 config,谁都能安全 import。
"""
from openai import AsyncOpenAI

from app.config import settings

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """懒加载 OpenAI 兼容客户端单例(指向中转站,chat + embedding 共用)。"""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    return _client
