import os
from dotenv import load_dotenv
from pydantic import SecretStr
from langchain_openai import ChatOpenAI

from ragas import SingleTurnSample, EvaluationDataset, evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness

load_dotenv()

judge = ChatOpenAI(
    model=os.environ["CHAT_MODEL"],
    api_key=SecretStr(os.environ["OPENAI_API_KEY"]),
    base_url=os.environ["OPENAI_BASE_URL"],
)
judge = LangchainLLMWrapper(judge)

sample = SingleTurnSample(
    user_input="chunk_size 和 chunk_overlap 会怎样影响 RAG 的召回效果?",
    retrieved_contexts=[
        "chunk_size 指每个文本块的最大长度。chunk_size 太大,单个块塞入过多内容,检索时定位精度会下降,容易召回不相关的信息。",
        "chunk_overlap 指相邻文本块之间的重叠长度。设置重叠是为了防止一句完整的话在切分时被从中间截断,导致上下文丢失。",
    ],
    response=(
        "chunk_size 越大,单个块包含的信息越多,但检索精度越低。"
        "chunk_overlap 通过让相邻块重叠来避免上下文被切断。"
        "此外,chunk_size 必须等于 embedding 的维度 1536。"
    ),
)

dataset = EvaluationDataset(samples=[sample])
result = evaluate(dataset, metrics=[Faithfulness()], llm=judge)
print(result)