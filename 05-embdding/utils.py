import numpy as np
from google import genai
from dotenv import load_dotenv
import ollama

load_dotenv()
client = genai.Client()  # 自动读取 GEMINI_API_KEY 或 GOOGLE_API_KEY

# 计算两个向量的余弦相似度
def cosine_similarity(a: list[float], b: list[float]) -> float:
    """返回 -1 到 1 之间的数，越大越相似"""
    vec_a, vec_b = np.array(a), np.array(b)
    return float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))


def get_embeddings(texts: list[str]) -> list[list[float]]:
    embeddings = []
    start = 0
    while start < len(texts):
        end = start + 20
        """批量获取 embedding"""
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=texts[start:end]
        )
        if result.embeddings:
            embeddings.extend(e.values for e in result.embeddings if e.values is not None)

        # result = ollama.embed(
        #     model='qwen3-embedding:0.6b',
        #     input=texts[start:end],
        # )
        # if result.embeddings:
            # embeddings.extend(result.embeddings)

        start = end
    return embeddings



def strip_chunks(chunks: list[str]) -> list[str]:
    return [chunk.strip() for chunk in chunks if chunk.strip()]

def get_each_chunk_len(chunks: list[str]) -> list[int]:
    return [len(chunk) for chunk in chunks]