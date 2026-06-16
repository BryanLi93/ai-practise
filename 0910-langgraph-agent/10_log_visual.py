from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END
from llm import get_chat_client
import time, json, functools

type TYPE_CATEGORY = Literal['chat', 'calc'] | None

def log_node(fn):
    @functools.wraps(fn)
    def wrapper(state):
        start = time.perf_counter()
        result = fn(state)                       # 真正跑节点
        dur_ms = (time.perf_counter() - start) * 1000
        print(json.dumps({
            "node": fn.__name__,
            "duration_ms": round(dur_ms, 1),
            "input": state,
            "output": result
        }, ensure_ascii=False, default=str))
        return result
    return wrapper

class MyState(TypedDict):
    query: str
    answer: str | None
    category: TYPE_CATEGORY

@log_node
def node_think(state: MyState) -> dict:
    print('in node_think')
    is_calc = any(char.isdigit() for char in state["query"])
    return { "category": "calc" if is_calc else "chat" }

@log_node
def node_calc(state: MyState) -> dict:
    print('in node_calc')
    return { "answer": "结果是10" }

@log_node
def node_chat(state: MyState) -> dict:
    print('in node_chat')
    response = get_chat_client().invoke(state["query"])
    return { "answer": response.content }

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

    graph.get_graph().draw_mermaid_png(output_file_path="output/10_log_visual.png")
