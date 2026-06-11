from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv()

_client: ChatOpenAI | None = None

def get_chat_client() -> ChatOpenAI:
    global _client
    if _client is None:
        _client = ChatOpenAI(
            model=os.environ["CHAT_MODEL"],
            api_key=SecretStr(os.environ["OPENAI_API_KEY"]),
            base_url=os.environ["OPENAI_BASE_URL"],
        )
    return _client
