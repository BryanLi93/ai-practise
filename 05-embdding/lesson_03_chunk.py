from lesson_02_ChromaDB import GoogleEmbedding, client, ask
from utils import strip_chunks, get_each_chunk_len
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_google_genai import GoogleGenerativeAIEmbeddings

chunk_size = 200
chunk_overlap = 50
long_article = """
大语言模型（LLM）的发展历程可以追溯到2017年Google发表的Transformer论文《Attention is All You Need》。这篇论文提出了自注意力机制，彻底改变了自然语言处理领域的研究方向。在此之前，循环神经网络（RNN）和长短期记忆网络（LSTM）是处理序列数据的主流方法，但它们存在难以并行计算和长距离依赖问题。

2018年，Google推出了BERT模型，这是第一个真正意义上的预训练语言模型。BERT通过双向编码器在大规模语料上进行预训练，然后在下游任务上微调，开创了"预训练+微调"的范式。同年，OpenAI发布了GPT-1，采用了单向解码器架构，虽然当时影响力不如BERT，但为后续的GPT系列奠定了基础。

2020年，OpenAI发布了GPT-3，拥有1750亿参数，展示了大语言模型的涌现能力。GPT-3最令人震惊的是它的少样本学习能力：不需要微调，只需要在提示词中给几个例子，就能完成各种任务。这标志着从"预训练+微调"向"预训练+提示"范式的转变。

2022年11月，ChatGPT的发布引爆了全球AI热潮。ChatGPT基于GPT-3.5，通过RLHF（人类反馈强化学习）技术进行了对齐训练，使得模型的输出更符合人类期望。两个月内用户数突破1亿，成为历史上增长最快的消费级应用。

2023年3月，OpenAI发布了GPT-4，这是一个多模态模型，能够同时处理文本和图像输入。GPT-4在各种专业考试中表现优异，在律师资格考试中排名前10%。同期，Google发布了PaLM 2和Gemini，Anthropic发布了Claude 2，Meta开源了LLaMA 2，大模型竞赛全面展开。

2024年以来，AI领域的焦点从单纯追求模型规模转向了实际应用。RAG（检索增强生成）技术让LLM能够利用外部知识库回答问题，减少幻觉。Agent框架让LLM能够使用工具、执行多步骤任务。MCP（模型上下文协议）标准化了LLM与外部系统的通信方式。这些技术的组合正在推动AI从"聊天机器人"向"智能助手"进化。

在中国市场，百度的文心一言、阿里的通义千问、字节跳动的豆包、月之暗面的Kimi、DeepSeek等产品竞争激烈。中国的AI应用场景非常丰富，从智能客服到代码生成，从内容创作到数据分析，AI应用工程师的需求持续增长。对于有前端开发经验的工程师来说，能够构建高质量的AI应用界面是一项稀缺且有价值的能力。
"""
questions = [
    "Transformer 是什么时候提出的？",
    "GPT-3 有什么突破？",
    "中国有哪些大模型？",
    "RAG 技术解决了什么问题？"
]

# 固定长度
def fixed_size_split(text: str, chunk_size: int = chunk_size, chunk_overlap: int = chunk_overlap) -> list[str]:
    """按固定字符数分块"""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap  # 下一个 chunk 的起点往回退 overlap 个字符
    return chunks

chunks_fixed = strip_chunks(fixed_size_split(long_article))

# collection_fixed = client.create_collection(
#     name="docs_fixed",
#     metadata={ "hnsw:space": "cosine" }, # 指定用余弦相似度
#     embedding_function=GoogleEmbedding()
# )
# collection_fixed.add(
#     ids=[f"id{i+1}" for i, _ in enumerate(chunks_fixed)],
#     documents=chunks_fixed,
# )

# print("策略1：固定长度---")
# print("chunk 数量：", len(chunks_fixed), "\n每个 chunk 长度：", get_each_chunk_len(chunks_fixed))
# for q in questions:
#     (q, a, _) = ask(collection_fixed, q)
#     print("\nQuestion：", q, "\nAnswer：", a[0])

'''
策略1：固定长度---
chunk 数量： 7 
每个 chunk 长度： [199, 200, 200, 198, 200, 200, 130]

Question： Transformer 是什么时候提出的？ 
Answer： 大语言模型（LLM）的发展历程可以追溯到2017年Google发表的Transformer论文《Attention is All You Need》。这篇论文提出了自注意力机制，彻底改变了自然语言处理领域的研究方向。在此之前，循环神经网络（RNN）和长短期记忆网络（LSTM）是处理序列数据的主流方法，但它们存在难以并行计算和长距离依赖问题。

2018年，Google推出了BERT模型，这是第一

Question： GPT-3 有什么突破？ 
Answer： 力不如BERT，但为后续的GPT系列奠定了基础。

2020年，OpenAI发布了GPT-3，拥有1750亿参数，展示了大语言模型的涌现能力。GPT-3最令人震惊的是它的少样本学习能力：不需要微调，只需要在提示词中给几个例子，就能完成各种任务。这标志着从"预训练+微调"向"预训练+提示"范式的转变。

2022年11月，ChatGPT的发布引爆了全球AI热潮。ChatGPT基于GPT-3.5，通过

Question： 中国有哪些大模型？ 
Answer： 实际应用。RAG（检索增强生成）技术让LLM能够利用外部知识库回答问题，减少幻觉。Agent框架让LLM能够使用工具、执行多步骤任务。MCP（模型上下文协议）标准化了LLM与外部系统的通信方式。这些技术的组合正在推动AI从"聊天机器人"向"智能助手"进化。

在中国市场，百度的文心一言、阿里的通义千问、字节跳动的豆包、月之暗面的Kimi、DeepSeek等产品竞争激烈。中国的AI应用场景非常丰富，

Question： RAG 技术解决了什么问题？ 
Answer： 实际应用。RAG（检索增强生成）技术让LLM能够利用外部知识库回答问题，减少幻觉。Agent框架让LLM能够使用工具、执行多步骤任务。MCP（模型上下文协议）标准化了LLM与外部系统的通信方式。这些技术的组合正在推动AI从"聊天机器人"向"智能助手"进化。

在中国市场，百度的文心一言、阿里的通义千问、字节跳动的豆包、月之暗面的Kimi、DeepSeek等产品竞争激烈。中国的AI应用场景非常丰富，
'''

# 递归
splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=50,
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
chunks_recursive = strip_chunks(splitter.split_text(long_article))

# collection_recursive = client.create_collection(
#     name="docs_recursive",
#     metadata={ "hnsw:space": "cosine" }, # 指定用余弦相似度
#     embedding_function=GoogleEmbedding()
# )
# collection_recursive.add(
#     ids=[f"id{i+1}" for i, _ in enumerate(chunks_recursive)],
#     documents=chunks_recursive,
# )

# print("策略2：递归---")
# print("chunk 数量：", len(chunks_recursive), "\n每个 chunk 长度：", get_each_chunk_len(chunks_recursive))
# for q in questions:
#     (q, a, _) = ask(collection_recursive, q)
#     print("\nQuestion：", q, "\nAnswer：", a[0])
'''
策略2：递归---
chunk 数量： 7 
每个 chunk 长度： [171, 150, 124, 115, 152, 155, 150]

Question： Transformer 是什么时候提出的？ 
Answer： 大语言模型（LLM）的发展历程可以追溯到2017年Google发表的Transformer论文《Attention is All You Need》。这篇论文提出了自注意力机制，彻底改变了自然语言处理领域的研究方向。在此之前，循环神经网络（RNN）和长短期记忆网络（LSTM）是处理序列数据的主流方法，但它们存在难以并行计算和长距离依赖问题。

Question： GPT-3 有什么突破？ 
Answer： 2020年，OpenAI发布了GPT-3，拥有1750亿参数，展示了大语言模型的涌现能力。GPT-3最令人震惊的是它的少样本学习能力：不需要微调，只需要在提示词中给几个例子，就能完成各种任务。这标志着从"预训练+微调"向"预训练+提示"范式的转变。

Question： 中国有哪些大模型？ 
Answer： 在中国市场，百度的文心一言、阿里的通义千问、字节跳动的豆包、月之暗面的Kimi、DeepSeek等产品竞争激烈。中国的AI应用场景非常丰富，从智能客服到代码生成，从内容创作到数据分析，AI应用工程师的需求持续增长。对于有前端开发经验的工程师来说，能够构建高质量的AI应用界面是一项稀缺且有价值的能力。

Question： RAG 技术解决了什么问题？ 
Answer： 2024年以来，AI领域的焦点从单纯追求模型规模转向了实际应用。RAG（检索增强生成）技术让LLM能够利用外部知识库回答问题，减少幻觉。Agent框架让LLM能够使用工具、执行多步骤任务。MCP（模型上下文协议）标准化了LLM与外部系统的通信方式。这些技术的组合正在推动AI从"聊天机器人"向"智能助手"进化。
'''


# 语义化
embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")
semantic_splitter = SemanticChunker(
    embeddings,
    breakpoint_threshold_type="percentile",  # 用百分位数判断突变
    breakpoint_threshold_amount=75,          # 相似度低于75分位的地方切割
    sentence_split_regex=r"(?<=[。！？；\n])",  # 在中文句末标点后切割
)
chunks_semantic = strip_chunks(semantic_splitter.split_text(long_article))

collection_semantic = client.create_collection(
    name="docs_semantic",
    metadata={ "hnsw:space": "cosine" }, # 指定用余弦相似度
    embedding_function=GoogleEmbedding()
)
collection_semantic.add(
    ids=[f"id{i+1}" for i in range(0, len(chunks_semantic))],
    documents=chunks_semantic,
)

print("策略3：语义化---")
print("chunk 数量：", len(chunks_semantic), "\n每个 chunk 长度：", get_each_chunk_len(chunks_semantic))
for q in questions:
    (q, a, _) = ask(collection_semantic, q)
    print("\nQuestion：", q, "\nAnswer：", a[0])

'''
策略3：语义化---
chunk 数量： 7 
每个 chunk 长度： [173, 152, 126, 117, 154, 159, 152]

Question： Transformer 是什么时候提出的？ 
Answer： 大语言模型（LLM）的发展历程可以追溯到2017年Google发表的Transformer论文《Attention is All You Need》。 这篇论文提出了自注意力机制，彻底改变了自然语言处理领域的研究方向。 在此之前，循环神经网络（RNN）和长短期记忆网络（LSTM）是处理序列数据的主流方法，但它们存在难以并行计算和长距离依赖问题。

Question： GPT-3 有什么突破？ 
Answer： 2020年，OpenAI发布了GPT-3，拥有1750亿参数，展示了大语言模型的涌现能力。 GPT-3最令人震惊的是它的少样本学习能力：不需要微调，只需要在提示词中给几个例子，就能完成各种任务。 这标志着从"预训练+微调"向"预训练+提示"范式的转变。

Question： 中国有哪些大模型？ 
Answer： 在中国市场，百度的文心一言、阿里的通义千问、字节跳动的豆包、月之暗面的Kimi、DeepSeek等产品竞争激烈。 中国的AI应用场景非常丰富，从智能客服到代码生成，从内容创作到数据分析，AI应用工程师的需求持续增长。 对于有前端开发经验的工程师来说，能够构建高质量的AI应用界面是一项稀缺且有价值的能力。

Question： RAG 技术解决了什么问题？ 
Answer： 2024年以来，AI领域的焦点从单纯追求模型规模转向了实际应用。 RAG（检索增强生成）技术让LLM能够利用外部知识库回答问题，减少幻觉。 Agent框架让LLM能够使用工具、执行多步骤任务。 MCP（模型上下文协议）标准化了LLM与外部系统的通信方式。 这些技术的组合正在推动AI从"聊天机器人"向"智能助手"进化。
'''