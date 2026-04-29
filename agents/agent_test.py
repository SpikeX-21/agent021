#!/usr/bin/env python3
"""
s01_agent_loop.py - The Agent Loop

The entire secret of an AI coding agent in one pattern:

    while stop_reason == "tool_use":
        response = LLM(messages, tools)
        execute tools
        append results

    +----------+      +-------+      +---------+
    |   User   | ---> |  LLM  | ---> |  Tool   |
    |  prompt  |      |       |      | execute |
    +----------+      +---+---+      +----+----+
                          ^               |
                          |   tool_result |
                          +---------------+
                          (loop continues)

This is the core loop: feed tool results back to the model
until the model decides to stop. Production agents layer
policy, hooks, and lifecycle controls on top.
"""

# -----------------------------------------------------------------------------
# 标准库导入
# -----------------------------------------------------------------------------
import os
import subprocess
import sys
sys.path.append("E:/Epic/agent021")

# -----------------------------------------------------------------------------
# 第三方库导入
# -----------------------------------------------------------------------------
from anthropic import Anthropic  # Anthropic API 客户端
from dotenv import load_dotenv  # 从 .env 文件加载环境变量
from tools.registry import ToolRegistry  # 工具注册表类
from tools.builtin.bash import BashTool  # Bash 工具类
# -----------------------------------------------------------------------------
# 环境变量初始化
# -----------------------------------------------------------------------------

# 加载 .env 文件中的环境变量（override=True 表示覆盖已存在的环境变量）
load_dotenv(override=True)

# 如果设置了自定义的 Anthropic API 基础 URL，则移除认证令牌
# 这通常用于使用代理或本地服务器时
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# 初始化 Anthropic 客户端，支持通过环境变量设置自定义基础 URL
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))

# 从环境变量读取模型 ID（必须在 .env 中设置 MODEL_ID）
MODEL = os.environ["MODEL_ID"]

# 系统提示词：定义 AI Agent 的角色和行为准则
SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

registry = ToolRegistry()  # 工具注册表实例
bashTool = BashTool()  # 创建 Bash 工具实例
registry.register_tool(bashTool)  # 将 Bash 工具注册到工具注册表中

# 工具定义：描述可用的工具及其参数规范（OpenAI 风格函数调用格式）
TOOLS = registry.get_all_tools_to_cc()  # 从工具注册表获取所有工具的定义

# -----------------------------------------------------------------------------
# 核心 Agent 循环
# -----------------------------------------------------------------------------

def agent_loop(messages: list):
    """
    核心 Agent 循环：与 LLM 交互并执行工具调用，直到模型停止。

    这是 AI Agent 的核心模式：
    1. 发送消息历史给 LLM
    2. 如果 LLM 返回工具调用请求，则执行工具并将结果追加到对话历史
    3. 重复步骤 1-2，直到 LLM 不再请求工具调用（stop_reason != "tool_use"）

    Args:
        messages: 对话历史列表，包含用户和助手的消息。
                  此列表会被原地修改，追加新的消息。

    Returns:
        None。结果通过修改传入的 messages 列表返回。
    """
    while True:
        # 调用 LLM API，传入对话历史、系统提示词和可用工具
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )

        # 将助手的响应（可能包含工具调用请求）追加到对话历史
        messages.append({"role": "assistant", "content": response.content})

        # 检查停止原因：如果不是工具调用，则任务完成，退出循环
        if response.stop_reason != "tool_use":
            return

        # 处理工具调用：遍历响应内容块，执行所有工具调用
        results = []
        for block in response.content:
            if block.type == "tool_use":
                # 打印模型生成的命令（黄色输出，用于调试）
                print(f"模型输出的命令\033[33m$ {block.input['command']}\033[0m")

                # 执行命令并获取输出
                output = registry.execute_tool(block.name, block.input)

                # 打印工具执行结果（限制前 200 字符）
                print("工具的执行结果 " + output[:200])

                # 构造工具结果消息（OpenAI 风格格式）
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output
                })

        # 将工具执行结果作为用户消息追加到对话历史
        # 这会触发下一次 LLM 调用，让模型基于工具结果继续处理
        messages.append({"role": "user", "content": results})


# -----------------------------------------------------------------------------
# 主程序入口
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # 初始化空对话历史
    history = []

    # 主交互循环：持续读取用户输入，直到用户退出
    while True:
        try:
            # 显示提示符（青色）并读取用户输入
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            # 处理 Ctrl+D (EOF) 或 Ctrl+C (中断) 信号，优雅退出
            break

        # 检查退出命令：q、exit 或空输入
        if query.strip().lower() in ("q", "exit", ""):
            break

        # 将用户输入作为消息追加到对话历史
        history.append({"role": "user", "content": query})

        # 调用 Agent 循环处理用户请求
        # 此函数会处理所有工具调用，直到模型完成响应
        agent_loop(history)

        # 获取最后一次响应内容并打印给
        response_content = history[-1]["content"]
        print("\033[32m模型的回复:\033[0m")

        # 处理响应内容块，提取并打印文本内容
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        print()
