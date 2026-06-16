from langgraph.graph import StateGraph, START, END
from typing import TypedDict
from langgraph.types import RetryPolicy

attempts = 0

class State(TypedDict):
    is_success: int

def node_flaky(state: State):
    global attempts
    print(f"第{attempts+1}次执行")

    # versionA: 可重试异常
    if attempts < 3:
        attempts += 1
        raise ConnectionError("连接异常")

    # versionB: 不重试异常
    # raise ValueError("数值错误")

    return { "is_success": 1 }

if __name__ == "__main__":
    builder = StateGraph(State)

    builder.add_node("node_flaky", node_flaky, retry_policy=RetryPolicy(max_attempts=4, retry_on=(ConnectionError, TimeoutError)))

    builder.add_edge(START, "node_flaky")
    builder.add_edge("node_flaky", END)

    graph = builder.compile()
    result = graph.invoke({ "is_success": 0 })
    print('result---', result)


