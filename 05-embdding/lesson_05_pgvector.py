import psycopg
from pgvector.psycopg import register_vector
import json
from utils import get_embeddings

# 连接数据库
conn = psycopg.connect(
    host="localhost",
    port=5432,
    user="postgres",
    password="postgres",
    dbname="ai_registry",
)

# # 注册 vector 类型，让 psycopg 知道怎么处理向量数据
# register_vector(conn)

# # 建表（如果不存在）
# conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
# conn.execute("""
#     CREATE TABLE IF NOT EXISTS documents (
#         id SERIAL PRIMARY KEY,
#         content TEXT NOT NULL,
#         metadata JSONB DEFAULT '{}',
#         embedding vector(3072)
#     )
# """)
# conn.commit()

# texts = [
#     "Python 是一门非常流行的编程语言",
#     "今天天气很好，适合出门散步",
#     "我最喜欢吃四川火锅",
#     "量子计算机可以解决经典计算机无法处理的问题",
# ]

# # 批量获取 embedding
# vectors = get_embeddings(texts)

# # 插入数据
# for text, vec in zip(texts, vectors):
#     conn.execute(
#         "INSERT INTO documents (content, metadata, embedding) VALUES (%s, %s, %s)",
#         (text, json.dumps({"source": "test"}), vec),
#     )
# conn.commit()

def search(query: str, top_k: int = 3) -> list[dict]:
    """语义搜索"""
    # 1. 获取查询文本的 embedding
    query_vec = get_embeddings([query])[0]
    
    # 2. 用余弦距离搜索最相似的 top_k 条
    results = conn.execute(
        """
        SELECT content, metadata, 1 - (embedding <=> %s::vector) AS similarity
        FROM documents
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (query_vec, query_vec, top_k),
    ).fetchall()
    
    return [
        {
            "content": row[0],
            "metadata": row[1],
            "similarity": round(row[2], 4),
        }
        for row in results
    ]

# 测试
results = search("编程语言")
for r in results:
    print(f"[{r['similarity']}] {r['content']}")