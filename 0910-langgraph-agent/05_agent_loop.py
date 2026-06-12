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

def node_llm(state: MessagesState) -> dict:
    print("in node llm")
    client = get_chat_client().bind_tools([add, multiply])
    message = client.invoke(state["messages"])
    return { "messages": [message] }

node_tool = ToolNode([add, multiply])

def should_continue(state: MessagesState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tool"
    return "end"

# -------- 手动实现循环 --------
# if __name__ == "__main__":
#     builder = StateGraph(MessagesState)

#     builder.add_node("llm", node_llm)
#     builder.add_node("tool", node_tool)

#     builder.add_edge(START, "llm")
#     builder.add_conditional_edges("llm", should_continue, {
#         "tool": "tool",
#         "end": END
#     })
#     builder.add_edge("tool", "llm")

#     graph = builder.compile()
#     result = graph.invoke({ "messages": [HumanMessage(content="3 加 5 的结果乘以3等于多少?")] })
#     print(result["messages"])

#     # 命令行打印
#     graph.get_graph().print_ascii()
#     # 复制到 mermaid.live
#     print(graph.get_graph().draw_mermaid())
    

# -------- Agent 实现循环 --------
if __name__ == "__main__":
   agent = create_agent(get_chat_client(), tools=[add, multiply]) 
   result = agent.invoke({ "messages": [HumanMessage("3加5的结果乘以3等于多少?")] })
   print(result["messages"])