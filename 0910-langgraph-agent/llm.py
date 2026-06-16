from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv()

_clients: dict[str, ChatOpenAI] = {}

def get_chat_client(model: str | None = None) -> ChatOpenAI:
    model = model or os.environ["CHAT_MODEL"]   # None 或空串都回落到默认
    if model not in _clients:                   # 按 model 名分桶:同 model 复用,不同 model 各一个
        _clients[model] = ChatOpenAI(
            model=model,
            api_key=SecretStr(os.environ["OPENAI_API_KEY"]),
            base_url=os.environ["OPENAI_BASE_URL"],
        )
    return _clients[model]
