import chromadb
from chromadb import EmbeddingFunction, Documents, Embeddings, Collection
from utils import get_embeddings

client = chromadb.Client()

article = """
人工智能（AI）是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。这些任务包括学习、推理、问题解决、感知和语言理解。

机器学习是人工智能的一个子领域，它使用统计方法让计算机从数据中学习，而不需要被明确编程。深度学习是机器学习的一个子集，使用多层神经网络来处理复杂的模式。

自然语言处理（NLP）是 AI 的一个重要应用领域，它使计算机能够理解、解释和生成人类语言。ChatGPT 和 Claude 等大语言模型是 NLP 领域的最新突破。

计算机视觉是另一个重要的 AI 应用领域，它使计算机能够从图像和视频中提取有意义的信息。自动驾驶汽车和人脸识别系统都依赖于计算机视觉技术。

强化学习是一种机器学习方法，智能体通过与环境交互来学习最优策略。AlphaGo 就是使用强化学习击败了人类围棋冠军。
"""

class GoogleEmbedding(EmbeddingFunction[Documents]):
    def __call__(self, input: Documents) -> Embeddings:
        return get_embeddings(input)

collection = client.create_collection(
    name="my_docs",
    metadata={ "hnsw:space": "cosine" }, # 指定用余弦相似度
    embedding_function=GoogleEmbedding()
)
# 注意 distances 的含义：当 hnsw:space 设为 cosine 时，ChromaDB 返回的是 1 - cosine_similarity，所以值越小越相似（0 = 完全相同，1 = 完全无关）。这和你 Day 1 的余弦相似度是反过来的，别搞混。


paragraphs = [p.strip() for p in article.split("\n\n") if p.strip()]
collection.add(
    ids=[f"id{i+1}" for i in range(0, len(paragraphs))],
    documents=paragraphs,
    metadatas=[{ "seq": i+1 } for i in range(0, len(paragraphs))]
)

def ask(collection: Collection, question: str) -> tuple[str, list[str], list[float]] | None:
    results = collection.query(
        query_texts=[question],
        n_results=1
    )
    if results["documents"] and results["distances"]:
        return (question, results["documents"][0], results["distances"][0])
    
questions= ["什么是深度学习？", "ChatGPT 属于哪个领域？", "AlphaGo 用了什么技术？", "自动驾驶和什么技术有关？"]

# for q in questions:
#     print(ask(collection, q))

"""
('什么是深度学习？', ['机器学习是人工智能的一个子领域，它使用统计方法让计算机从数据中学习，而不需要被明确编程。深度学习是机器学习的一个子集，使用多层神经网络来处理复杂的模式。'], [0.23521965742111206])
('ChatGPT 属于哪个领域？', ['自然语言处理（NLP）是 AI 的一个重要应用领域，它使计算机能够理解、解释和生成人类语言。ChatGPT 和 Claude 等大语言模型是 NLP 领域的最新突破。'], [0.26310938596725464])
('AlphaGo 用了什么技术？', ['强化学习是一种机器学习方法，智能体通过与环境交互来学习最优策略。AlphaGo 就是使用强化学习击败了人类围棋冠军。\n'], [0.25508445501327515])
('自动驾驶和什么技术有关？', ['计算机视觉是另一个重要的 AI 应用领域，它使计算机能够从图像和视频中提取有意义的信息。自动驾驶汽车和人脸识别系统都依赖于计算机视觉技术。'], [0.31702685356140137])
"""