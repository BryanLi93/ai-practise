from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from llm import get_chat_client
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver

def node_chat(state: MessagesState) -> dict:
    response = get_chat_client().invoke(state["messages"])
    return { "messages": [response] }

# -------- InMemorySaver --------
# if __name__ == "__main__":
#     builder = StateGraph(MessagesState)

#     builder.add_node("node_chat", node_chat)

#     builder.add_edge(START, "node_chat")
#     builder.add_edge("node_chat", END)

#     graph = builder.compile(checkpointer=InMemorySaver())

#     config: RunnableConfig = { "configurable": { "thread_id": "1" } }
#     result1 = graph.invoke({"messages": [SystemMessage(content="你是一个简洁回答的助手"), HumanMessage(content="我叫小明")]}, config=config)
#     print("round1 result---", result1["messages"][-1].content)
#     result2 = graph.invoke({ "messages": [HumanMessage(content="我是谁？")]}, config=config)
#     print("round3 with history---", result2["messages"][-1].content)

#     config3: RunnableConfig = { "configurable": { "thread_id": "2" } }
#     result3 = graph.invoke({ "messages": [HumanMessage(content="我是谁？")]}, config=config3)
#     print("round2 without history---", result3["messages"][-1].content)
    
# -------- SqliteSaver --------
if __name__ == "__main__":
    builder = StateGraph(MessagesState)

    builder.add_node("node_chat", node_chat)

    builder.add_edge(START, "node_chat")
    builder.add_edge("node_chat", END)

    with SqliteSaver.from_conn_string("checkpoints.db") as checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
        
        config: RunnableConfig = { "configurable": { "thread_id": "1" } }
        # result1 = graph.invoke({"messages": [SystemMessage(content="你是一个简洁回答的助手"), HumanMessage(content="我叫小明")]}, config=config)
        # print("round1 result---", result1["messages"][-1].content)
        result2 = graph.invoke({ "messages": [HumanMessage(content="我是谁？")]}, config=config)
        print("round3 with history---", result2["messages"][-1].content)
