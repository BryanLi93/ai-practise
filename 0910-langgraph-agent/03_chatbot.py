from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from llm import get_chat_client

def node_chat(state: MessagesState) -> dict:
    response = get_chat_client().invoke(state["messages"])
    return { "messages": [response] }

if __name__ == "__main__":
    builder = StateGraph(MessagesState)

    builder.add_node("node_chat", node_chat)

    builder.add_edge(START, "node_chat")
    builder.add_edge("node_chat", END)

    graph = builder.compile()
    result1 = graph.invoke({"messages": [SystemMessage(content="你是一个简洁回答的助手"), HumanMessage(content="我叫小明")]})
    print("round1 result---", result1["messages"][-1].content)

    result2 = graph.invoke({ "messages": [HumanMessage(content="我是谁？")]})
    print("round2 without history---", result2["messages"][-1].content)
    
    result3 = graph.invoke({ "messages": result1["messages"] + [HumanMessage(content="我是谁？")]})
    print("round3 with history---", result3["messages"][-1].content)

