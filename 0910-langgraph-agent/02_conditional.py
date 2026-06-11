from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END

type TYPE_CATEGORY = Literal['chat', 'calc'] | None

class MyState(TypedDict):
    query: str
    answer: str | None
    category: TYPE_CATEGORY

def node_think(state: MyState) -> dict:
    print('in node_think')
    is_calc = any(char.isdigit() for char in state["query"])
    return { "category": "calc" if is_calc else "chat" }

def node_calc(state: MyState) -> dict:
    print('in node_calc')
    return { "answer": "结果是10" }

def node_chat(state: MyState) -> dict:
    print('in node_chat')
    return { "answer": "你好👋" }

def route_think(state: MyState) -> TYPE_CATEGORY:
    return state["category"]

if __name__ == "__main__":
    builder = StateGraph(MyState)

    builder.add_node("node_think", node_think)
    builder.add_node("node_calc", node_calc)
    builder.add_node("node_chat", node_chat)

    builder.add_edge(START, "node_think")
    builder.add_conditional_edges(
        "node_think",
        route_think,
        {
            "chat": "node_chat",
            "calc": "node_calc"
        }
    )
    builder.add_edge("node_chat", END)
    builder.add_edge("node_calc", END)

    graph = builder.compile()
    result_chat = graph.invoke({ "query": "今天天气不错", "answer": None, "category": None })
    print("query chat---", result_chat)

    result_calc = graph.invoke({ "query": "5+5=?", "answer": None, "category": None })
    print("query calc---", result_calc)
