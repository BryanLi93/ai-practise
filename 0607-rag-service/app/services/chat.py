import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message
from app.llm import get_openai_client
from app.config import settings
from app.services.retrieval import query as run_query
from app.services import conversation as conv_service
from app.schemas import Source, QueryResponse

logger = logging.getLogger(__name__)


class ConversationNotFound(Exception):
    """请求指定了 conversation_id 但库里不存在;由 router 映射成 404。"""

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
    client = get_openai_client()
    messages = [f"{m.role}:{m.content}" for m in recent_messages]

    user_prompt = REWRITE_USER_PROMPT_TEMPLATE.format(question=question, messages="\n".join(messages))
    response = await client.chat.completions.create(
        model=settings.chat_model,
        messages=[
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=256,
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM returned empty response")

    return content.strip()

async def handle_chat(
    db: AsyncSession,
    req_conversation_id: uuid.UUID | None,
    req_question: str,
    req_top_k: int,
) -> QueryResponse:
    """
    多轮对话编排:解析会话 → 改写 → 检索生成 →(成功后)落库。

    - 所有 DB 写操作都放在 RAG 成功之后,中途失败一个字都不写,不留空会话。
    - 不在这里管 HTTP 状态码:会话不存在抛 ConversationNotFound,由 router 翻译成 404。
    """
    # 1. 解析会话 + 加载历史(只读,不写库)
    recent_messages: list[Message] = []
    if req_conversation_id is not None:
        if not await conv_service.conversation_exists(db, req_conversation_id):
            raise ConversationNotFound(str(req_conversation_id))
        recent_messages = await conv_service.get_recent_messages(db, conversation_id=req_conversation_id)

    # 2. 有历史才改写(第一轮没历史,省一次 LLM 调用)
    search_query = req_question
    if recent_messages:
        search_query = await rewrite_query(req_question, recent_messages)
        logger.info("rewrite: %r -> %r", req_question, search_query)

    # 3. 检索 + 生成(无 DB 写入)
    result = await run_query(
        db,
        question=req_question,
        search_query=search_query,
        recent_messages=recent_messages,
        top_k=req_top_k,
    )

    # 4. 组装 sources(落库的 sources_json 和响应共用同一份)
    sources = [
        Source(
            id=i,
            chunk_id=rc.chunk.id,
            document_id=rc.document.id,
            document_filename=rc.document.filename,
            chunk_index=rc.chunk.chunk_index,
            content=rc.chunk.content,
            similarity=round(rc.similarity, 4),
            vector_rank=rc.vector_rank,
            keyword_rank=rc.keyword_rank,
            rerank_score=rc.rerank_score,
        )
        for i, rc in enumerate(result.sources, start=1)
    ]

    # 5. RAG 成功后才写库:会话 + 两条消息,放进一个事务一次提交
    if req_conversation_id is None:
        conv = await conv_service.create_conversation(db, title=req_question[:50], commit=False)
        conversation_id = conv.id
    else:
        conversation_id = req_conversation_id

    await conv_service.add_message(
        db, conversation_id=conversation_id, role="user",
        content=req_question, commit=False,
    )
    await conv_service.add_message(
        db, conversation_id=conversation_id, role="assistant",
        content=result.answer, sources=[s.model_dump() for s in sources],
        commit=False,
    )
    await db.commit()

    # 6. 返回
    return QueryResponse(answer=result.answer, sources=sources, conversation_id=conversation_id)

