import operator
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, START, END

class MyState(TypedDict):
    steps: Annotated[list[str], operator.add]
    
def node_a(state: MyState) -> dict:
    print("in node_a")
    return { "steps": ["node_a executed"] }

def node_b(state: MyState) -> dict:
    print("in node_b")
    return { "steps": ["node_b executed"] }


if __name__ == "__main__":
    builder = StateGraph(MyState)
    builder.add_node("node_a", node_a)
    builder.add_node("node_b", node_b)

    builder.add_edge(START, "node_a")
    builder.add_edge("node_a", "node_b")
    builder.add_edge("node_b", END)

    graph = builder.compile()

    result = graph.invoke({ "steps": [] })
    print(result)