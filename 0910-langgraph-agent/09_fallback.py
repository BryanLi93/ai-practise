from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import ToolNode
from langchain.agents import create_agent

from llm import get_chat_client

@tool
def add(a: int, b: int) -> int:
    """把两个整数相加""" # ← docstring 必写!LLM 靠它理解"这工具是干嘛的"
    return a + b

@tool
def multiply(a: int, b: int) -> int:
     """把两个整数相乘"""
     return a*b

if __name__ == "__main__":
    backup = get_chat_client()

    client = get_chat_client(model="wrong_model").with_fallbacks([backup])
    # create_agent 的 model 类型只声明了 str | BaseChatModel,
    # 但运行时对传入对象调 .bind_tools() 即可,RunnableWithFallbacks 靠代理扛得住。
    # 这里是已知的类型签名偏窄,运行时无误,精确压掉这一条。
    agent = create_agent(client, tools=[add, multiply])  # pyright: ignore[reportCallIssue, reportArgumentType]
    result = agent.invoke({ "messages": [HumanMessage("3加5的结果乘以3等于多少?")] })
    print(result["messages"][-1].content)