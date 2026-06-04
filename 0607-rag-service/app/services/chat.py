from google.genai import types

from app.models import Message
from app.embedding import get_client as get_genai_client
from app.config import settings

REWRITE_SYSTEM_PROMPT = """你是一个问题改写助手。根据对话历史,把用户的最新问题改写成一个不依赖上下文、能独立理解的完整问题。

规则:
- 消解所有指代(它/这个/那个等),替换成具体名词
- 补全省略的主语和宾语
- 如果最新问题本身已经完整独立,原样返回
- 只输出改写后的问题本身,不要解释,不要加引号,不要回答问题"""

REWRITE_USER_PROMPT_TEMPLATE = """
根据用户当前问题和之前的聊天记录，生成完整的问题
---
当前问题：{question}
---
聊天记录：{messages}

"""


async def rewrite_query(question: str, recent_messages: list[Message]) -> str:
    # 查询重写
    client = get_genai_client()
    messages = [f"{m.role}:{m.content}" for m in recent_messages]

    user_prompt = REWRITE_USER_PROMPT_TEMPLATE.format(question=question, messages="\n".join(messages))
    response = await client.aio.models.generate_content(
        model=settings.chat_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=REWRITE_SYSTEM_PROMPT,
            temperature=0.1,
            max_output_tokens=256,
        )
    )

    if not response.text:
        raise RuntimeError("LLM returned empty response")

    return response.text.strip()