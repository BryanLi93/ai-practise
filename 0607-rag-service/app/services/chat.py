from google.genai import types

from app.models import Message
from app.embedding import get_client as get_genai_client
from app.config import settings

REWRITE_SYSTEM_PROMPT = """你是一个用户问题改写助手
"""

REWRITE_USER_PROMPT_TEMPLATE = """
根据用户当前问题和之前的聊天记录，生成完整的问题
---
当前问题：{question}
---
聊天记录：{messages}

"""


async def rewrite_query(question: str, history: list[Message]) -> str:
    # 查询重写
    client = get_genai_client()
    messages = [f"{m.role}:{m.content}" for m in history]

    user_prompt = REWRITE_USER_PROMPT_TEMPLATE.format(question=question, messages="\n".join(messages))
    response = await client.aio.models.generate_content(
        model=settings.chat_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=REWRITE_SYSTEM_PROMPT,
            temperature=0.1,
            max_output_tokens=1024,
        )
    )

    if not response.text:
        raise RuntimeError("LLM returned empty response")

    return response.text.strip()