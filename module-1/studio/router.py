
from langchain_openai import AzureChatOpenAI
from langgraph.graph import MessagesState
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
import os
 
# Tool
def multiply(a: int, b: int) -> int:
    """Multiplies a and b.
 
    Args:
        a: first int
        b: second int
    """
    return a * b
 
# LLM with bound tool (Azure)
llm = AzureChatOpenAI(
            model=os.getenv('AZURE_OPENAI_DEPLOYMENT'),
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_version="2025-04-01-preview",
        )
 
 
llm_with_tools = llm.bind_tools([multiply])
 
# Node
def tool_calling_llm(state: MessagesState):
    return {"messages": [llm_with_tools.invoke(state["messages"])]}
 
# Build graph
builder = StateGraph(MessagesState)
builder.add_node("tool_calling_llm", tool_calling_llm)
builder.add_node("tools", ToolNode([multiply]))
builder.add_edge(START, "tool_calling_llm")
builder.add_conditional_edges(
    "tool_calling_llm",
    tools_condition,
)
builder.add_edge("tools", END)
 
# Compile graph
graph = builder.compile()
 