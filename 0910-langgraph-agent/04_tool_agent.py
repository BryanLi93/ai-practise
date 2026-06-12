from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import ToolNode

from llm import get_chat_client




@tool
def add(a: int, b: int) -> int:
    """把两个整数相加""" # ← docstring 必写!LLM 靠它理解"这工具是干嘛的"
    return a + b

def node_llm(state: MessagesState) -> dict:
    print("in node llm")
    client = get_chat_client().bind_tools([add])
    message = client.invoke(state["messages"])
    return { "messages": [message] }

node_tool = ToolNode([add])


if __name__ == "__main__":
    # response_without_tool = llm_with_tools.invoke("你好")
    # print("tool_calls--- without tool", response_without_tool.tool_calls)
    # print("content--- without tool", response_without_tool.content)

    builder = StateGraph(MessagesState)

    builder.add_node("llm", node_llm)
    builder.add_node("tool", node_tool)
    builder.add_node("resp", node_llm)

    builder.add_edge(START, "llm")
    builder.add_edge("llm", "tool")
    builder.add_edge("tool", "resp")
    builder.add_edge("resp", END)

    graph = builder.compile()
    result = graph.invoke({ "messages": [HumanMessage(content="3 加 5 等于几?")] })
    print(result["messages"])

    graph.get_graph().print_ascii()
    