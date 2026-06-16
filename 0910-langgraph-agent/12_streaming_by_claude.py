"""
Step 11:流式输出 —— 用 astream + stream_mode="messages" 做打字机效果
对照 rag-service 的 SSE token 流。

跑:.venv/bin/python 12_streaming.py
"""
import asyncio
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, AIMessageChunk

from llm import get_chat_client

# 最简 chat agent(不带工具,专注看 token 流;带不带工具,流式机制都一样)
agent = create_agent(
    get_chat_client(),
    tools=[],
    system_prompt="你是一个简洁的助手,用中文回答",
)

QUESTION = "用三句话介绍一下 pgvector 是什么"


async def typewriter():
    """astream + messages 模式:token 逐个到,拼成打字机效果(这一步的主角)"""
    print("===== astream / messages(打字机)=====")
    # astream 是【异步生成器】,只能用 async for 取;每个 item 是二元组 (消息块, 元数据)
    async for chunk, metadata in agent.astream(
        {"messages": [HumanMessage(QUESTION)]},
        stream_mode="messages",
    ):
        # 只要 AI 生成的、且有内容的块;tool 块 / 空块(纯 tool_call 那步)跳过
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            # end="" 不换行、flush=True 立刻冲到终端 —— 缺一个就又变回整段出现
            print(chunk.content, end="", flush=True)
    print()  # 整段打完收个尾换行


def compare_updates_vs_messages():
    """同一个问题,updates(整段) vs messages(逐 token),亲眼看粒度差别"""
    print("\n===== stream / updates(节点粒度:整段一次到)=====")
    for update in agent.stream(
        {"messages": [HumanMessage(QUESTION)]},
        stream_mode="updates",
    ):
        # updates:每个 chunk = {节点名: {"messages": [整条消息]}}
        for node_name, payload in update.items():
            for msg in payload.get("messages", []):
                print(f"[{node_name}] {msg.content}")

    print("\n===== stream / messages(token 粒度:逐个到,同步版)=====")
    # 注意:sync 的 .stream() 一样能逐 token,messages 模式不是 astream 专属
    for chunk, metadata in agent.stream(
        {"messages": [HumanMessage(QUESTION)]},
        stream_mode="messages",
    ):
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            print(chunk.content, end="", flush=True)
    print()


if __name__ == "__main__":
    # astream 是异步生成器,必须放进事件循环里跑(asyncio.run 起循环 → 跑完 → 关循环)
    asyncio.run(typewriter())

    # 对照:同一条流,updates 是整段、messages 是逐 token
    compare_updates_vs_messages()
