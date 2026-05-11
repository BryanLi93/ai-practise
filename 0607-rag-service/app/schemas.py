"""
API 请求/响应 schemas。

设计原则:
- 输入用 Request,输出用 Response,清晰区分
- 内部 ORM 模型(models.py)和 API schema(这里)解耦
- Day 1-2 暂不做引用溯源,sources 字段留到 Day 3 再加
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

# ---------- Upload 端点 ----------

class UploadResponse(BaseModel):
    """文件上传成功的响应。"""
    document_id: int = Field(description="新创建的 document 主键")
    filename: str = Field(description="文件名")
    chunk_count: int = Field(description="切分后的 chunk 数量")
    created_at: datetime = Field(description="入库时间")

# ---------- Query 端点 ----------

class QueryRequest(BaseModel):
    """用户提问。"""
    question: str = Field(
        min_length=1,
        max_length=1000,
        description="用户问题,1-1000 字符",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="检索返回的 chunk 数量,默认 5",
    )

class Source(BaseModel):
    """检索到的 chunk 引用信息。"""
    id: int = Field(description="引用编号,对应 answer 中的 [n] 标记")
    chunk_id: int = Field(description="chunks 表主键")
    document_id: int = Field(description="所属文档 id")
    document_filename: str = Field(description="文档名")
    chunk_index: int = Field(description="chunk 在文档内的顺序")
    content: str = Field(description="chunk 内容")
    similarity: float = Field(description="相似度分数 0-1,越高越相关")


class QueryResponse(BaseModel):
    """RAG 答案。"""
    answer: str = Field(description="基于检索内容生成的答案")
    sources: list[Source] = Field(description="答案引用的 chunks 列表")