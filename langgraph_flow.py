from langgraph.graph import StateGraph
from agents import analyze_code
from orchestrator import orchestrate_results
from typing import TypedDict, Any

try:
    with open("guidelines.txt", "r", encoding="utf-8") as f:
        GUIDELINES = f.read()
except Exception as e:
    print("⚠️ Failed to load guidelines.txt:", e)
    GUIDELINES = ""


class GraphState(TypedDict, total=False):
    chunk: Any
    security: str
    performance: str
    style: str
    final: list


def security_node(state: GraphState) -> GraphState:
    code = state["chunk"]["code"]
    result = analyze_code("security", code, GUIDELINES)
    print("SECURITY RESULT:", result)
    return {"security": result or ""}


def performance_node(state: GraphState) -> GraphState:
    code = state["chunk"]["code"]
    result = analyze_code("performance", code, GUIDELINES)
    print("PERFORMANCE RESULT:", result)
    return {"performance": result or ""}


def style_node(state: GraphState) -> GraphState:
    code = state["chunk"]["code"]
    result = analyze_code("style", code, GUIDELINES)
    print("STYLE RESULT:", result)
    return {"style": result or ""}


def orchestrator_node(state: GraphState) -> GraphState:
    results = [{
        "chunk": state.get("chunk", {}),
        "analysis": {
            "security": state.get("security", ""),
            "performance": state.get("performance", ""),
            "style": state.get("style", "")
        }
    }]
    final = orchestrate_results(results)
    return {"final": final if final else []}


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("security", security_node)
    graph.add_node("performance", performance_node)
    graph.add_node("style", style_node)
    graph.add_node("orchestrator", orchestrator_node)

    graph.set_entry_point("security")
    graph.add_edge("security", "performance")
    graph.add_edge("performance", "style")
    graph.add_edge("style", "orchestrator")
    graph.set_finish_point("orchestrator")

    return graph.compile()
