import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter
from lesson_02_ChromaDB import GoogleEmbedding, client, ask


def extract_pages(pdf_path: str) -> list[dict[str, str | int]]:
    """按页提取，保留页码"""
    pages: list[dict[str, str | int]] = []
    with fitz.open(pdf_path) as doc:
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:  # 跳过空白页
                pages.append({
                    "page": page_num,
                    "text": text,
                })
    return pages

def pdf_to_chunks(
    pdf_path: str,
    chunk_size: int = 300,
    chunk_overlap: int = 50,
) -> list[dict[str, str | int]]:
    """PDF → 文本提取 → 分块，每个 chunk 带页码"""
    
    # 1. 按页提取文本
    pages = extract_pages(pdf_path)
    
    # 2. 对每页文本分块
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=[
            "\n\n",      # 段落
            "\n",        # 换行
            "。", "！", "？", "；",  # 中文句末/分句
            ". ", "! ", "? ", "; ",  # 英文句末（带空格，避免切到 "GPT-3.5" 的点）
            "，", "、",  # 中文逗号、顿号
            ", ",        # 英文逗号
            " ",         # 空格
            "",          # 兜底
        ]
    )
    
    chunks: list[dict[str, str | int]] = []
    for page_data in pages:
        page_chunks = splitter.split_text(str(page_data["text"]))
        for chunk_text in page_chunks:
            chunk_text = chunk_text.strip()
            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "page": page_data["page"],
                })
    
    return chunks
    
pdf_path = "./Animal_Farm.pdf"

chunks = pdf_to_chunks(pdf_path)
collection = client.create_collection(
    name="docs",
    metadata={ "hnsw:space": "cosine" }, # 指定用余弦相似度
    embedding_function=GoogleEmbedding()
)
collection.add(
    ids=[f"id{i+1}" for i, _ in enumerate(chunks)],
    documents=[str(chunk["text"]) for chunk in chunks],
    metadatas=[{ "page": chunk["page"] } for chunk in chunks ]
)

questions= ["七诫是哪七诫", "拳击手是谁？", "拿破仑是谁"]

for q in questions:
    print(ask(collection, q))
