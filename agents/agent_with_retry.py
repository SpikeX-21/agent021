#!/usr/bin/env python3
"""
agent_with_retry.py - 带指数退避重试的健壮 Agent

在基础 Agent 循环之上，叠加三层健壮性保障：

1. API 调用重试（指数退避 + 抖动）：针对可重试的 HTTP 状态码
   （429 限流、500/503 服务器侧错误）自动重试，避免瞬时故障让 Agent 直接退出。

2. 循环保护：用 MAX_ITERATIONS 限制单次会话内的最大迭代次数，
   防止模型陷入死循环或无意义的工具调用风暴。

3. 工具容错：工具抛出的异常会被捕获并作为 tool_result 回传给模型，
   让模型有机会自行纠偏，而不是让整个 Agent 崩溃。

改编自 OpenAI SDK 版本的 TypeScript 实现，适配 Anthropic Claude SDK 的差异：
    OpenAI.APIError        ->  anthropic.APIStatusError
    err.status             ->  err.status_code
    setTimeout/Promise     ->  time.sleep
    message.tool_calls     ->  response.content 中的 tool_use block
    role="tool" 消息       ->  role="user" + tool_result content block
"""

# -----------------------------------------------------------------------------
# 标准库导入
# -----------------------------------------------------------------------------
import os
import json
import random
import sys
import time
from typing import Any, Dict
sys.path.append("E:/Epic/agent021")

# -----------------------------------------------------------------------------
# 第三方库导入
# -----------------------------------------------------------------------------
from anthropic import Anthropic, APIStatusError  # Anthropic 客户端与带状态码的错误基类
from dotenv import load_dotenv  # 从 .env 文件加载环境变量
from tools.registry import ToolRegistry  # 工具注册表类
from tools.builtin.bash import BashTool  # Bash 工具类
from tools.base import Tool, ToolParameter  # 工具基类（用于内联定义模拟工具）
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
SYSTEM = (
    f"You are a coding agent at {os.getcwd()}. "
    "You can use bash to run shell commands, and use query_database to look up "
    "records (table=users|orders, id=int). The database tool is flaky and may "
    "occasionally raise a transient timeout error — when that happens, retry the "
    "same call until it succeeds. Act, don't explain."
)

registry = ToolRegistry()  # 工具注册表实例
bashTool = BashTool()  # 创建 Bash 工具实例
registry.register_tool(bashTool)  # 将 Bash 工具注册到工具注册表中


# -----------------------------------------------------------------------------
# 模拟工具：query_database（30% 概率抛错，用于测试工具级容错与模型自重试）
# -----------------------------------------------------------------------------

class QueryDatabaseTool(Tool):
    """模拟数据库查询工具：30% 概率抛出超时错误，用于演示工具失败回路。

    与 TS 版本 query_database 行为对齐：
    - 支持 table=users / orders 两张表
    - 命中记录返回字符串描述；未命中返回友好提示
    - 30% 概率抛 RuntimeError 模拟瞬时数据库连接超时
    """

    _RECORDS = {
        "users": {
            1: "Alice (alice@example.com)",
            2: "Bob (bob@example.com)",
        },
        "orders": {
            101: "Order #101: 3x TypeScript Book, $89.00",
            102: "Order #102: 1x Mechanical Keyboard, $159.00",
        },
    }

    def __init__(self):
        super().__init__(
            name="query_database",
            description="查询数据库中的记录。table 支持 users 和 orders，id 为记录编号",
        )

    def get_parameters(self):
        return [
            ToolParameter(
                name="table",
                type="string",
                description="表名：users 或 orders",
                required=True,
            ),
            ToolParameter(
                name="id",
                type="integer",
                description="记录 ID",
                required=True,
            ),
        ]

    def run(self, parameters: Dict[str, Any]) -> str:
        table = parameters["table"]
        record_id = int(parameters["id"])

        # 30% 概率抛出"瞬时"错误，让 registry 把异常转成错误字符串回传给模型
        if random.random() < 0.9:
            raise RuntimeError(
                f"Database connection timeout: failed to query {table}#{record_id}"
            )

        return (
            self._RECORDS.get(table, {}).get(record_id)
            or f"No record found in {table} with id={record_id}"
        )


registry.register_tool(QueryDatabaseTool())  # 注册模拟数据库工具

# 工具定义：描述可用的工具及其参数规范（OpenAI 风格函数调用格式）
TOOLS = registry.get_all_tools_to_cc()  # 从工具注册表获取所有工具的定义

# -----------------------------------------------------------------------------
# 重试与循环保护配置
# -----------------------------------------------------------------------------

# API 重试配置（与 TS 版本保持一致的语义）
MAX_ATTEMPTS = 4          # 最大尝试次数（含首次调用）
BASE_DELAY = 1.0          # 基础退避时间，单位：秒
JITTER = 0.5              # 抖动上限，单位：秒（避免雪崩式重试）
MAX_DELAY = 30.0          # 单次等待时间上限，单位：秒

# Agent 循环保护：单次任务最多迭代次数，防止模型陷入死循环
MAX_ITERATIONS = 10

# 可重试的 HTTP 状态码：限流与服务器侧瞬时故障
RETRYABLE_STATUS = {429, 500, 503}

# 同参工具循环检测阈值（按 (name, 规范化 input) 计数；is_error 的回合不计数）
TOOL_LOOP_SOFT_K = 3   # 累计达到此数：在 tool_result 末尾注入软提示，让模型自己跳出
TOOL_LOOP_HARD_K = 5   # 累计达到此数：处理完本轮工具后强制 return，兜底防止失控


def _tool_signature(name: str, tool_input: Any) -> str:
    """把一次工具调用规范化成可比较的签名串。

    使用 json.dumps + sort_keys 保证 input 字典顺序不同也算同一签名；
    default=str 兜底处理非 JSON 原生类型；序列化失败时 fallback 到 str()。
    """
    try:
        payload = json.dumps(tool_input, sort_keys=True, default=str, ensure_ascii=False)
    except Exception:
        payload = str(tool_input)
    return f"{name}|{payload}"

## 针对大模型sdk调用api时候的错误 进行的重试
def with_retry(fn, max_attempts: int = MAX_ATTEMPTS):
    """
    对一次 API 调用包装指数退避重试。

    重试规则：
    - 仅对 anthropic.APIStatusError 中状态码命中 RETRYABLE_STATUS 的错误重试。
    - 非 API 错误、不可重试状态码：直接抛出，不浪费配额。
    - 退避时间 = base * 2^attempt + 随机抖动，并被 MAX_DELAY 截断。

    Args:
        fn: 无参可调用对象，内部发起一次 API 请求。
        max_attempts: 最大尝试次数（包含首次调用）。

    Returns:
        fn() 的返回值。

    Raises:
        最后一次失败的异常（达到最大尝试次数后）或不可重试的异常。
    """
    last_error = None

    for attempt in range(max_attempts):
        try:
            return fn()
        except APIStatusError as err:
            last_error = err

            # 不可重试的状态码：立即抛出
            status = getattr(err, "status_code", None)
            if status not in RETRYABLE_STATUS:
                raise

            # 已是最后一次尝试，跳出循环抛出原错误
            if attempt == max_attempts - 1:
                break

            # 计算退避延迟：指数 + 抖动，并截断到 MAX_DELAY
            exponential = BASE_DELAY * (2 ** attempt)
            jitter = random.random() * JITTER
            delay = min(exponential + jitter, MAX_DELAY)

            err_type = type(err).__name__
            print(
                f"[retry] attempt {attempt + 1}/{max_attempts} failed "
                f"({status} {err_type}). Waiting {delay:.2f}s..."
            )
            time.sleep(delay)
        except Exception:
            # 非 API 错误（网络层之外的本地 bug 等）不重试
            raise

    raise last_error

# -----------------------------------------------------------------------------
# 核心 Agent 循环
# -----------------------------------------------------------------------------

def agent_loop(messages: list):
    """
    带重试与循环保护的 Agent 主循环。

    在基础 "tool_use 直至停止" 模式上叠加：
    1. API 调用经 with_retry 包装，对 429/500/503 自动指数退避重试；
    2. 用 MAX_ITERATIONS 限制最大迭代次数，防止死循环；
    3. 工具异常被捕获并以 tool_result(is_error=True) 回传给模型；
    4. 同参工具循环检测：连续相同签名达到 SOFT_K 注入软提示，达到 HARD_K 强制终止。

    Args:
        messages: 对话历史列表，原地追加助手响应与工具结果。
    """
    # 同参工具循环计数器：仅成功调用计数，is_error=True 视为合法重试不计入
    tool_call_counts: Dict[str, int] = {}
    aborted_by_loop = False

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n[loop] iteration {iteration}/{MAX_ITERATIONS}")

        # 调用 LLM API，带重试保护
        response = with_retry(lambda: client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        ))

        # 将助手的响应（可能包含工具调用请求）追加到对话历史
        messages.append({"role": "assistant", "content": response.content})

        # 检查停止原因：如果不是工具调用，则任务完成，退出循环
        if response.stop_reason != "tool_use":
            return

        # 处理工具调用：遍历响应内容块，执行所有工具调用
        results = []
        for block in response.content:
            if block.type == "tool_use":
                # 打印模型的工具调用（黄色输出，用于调试）
                # 对 bash 单独显示命令行，其它工具显示完整入参
                if block.name == "bash" and isinstance(block.input, dict) and "command" in block.input:
                    print(f"模型输出的命令\033[33m$ {block.input['command']}\033[0m")
                else:
                    print(f"模型调用工具\033[33m{block.name}({block.input})\033[0m")

                # 执行工具：捕获异常作为 tool_result 回传，避免整个 Agent 崩溃
                try:
                    output = registry.execute_tool(block.name, block.input)
                    is_error = False
                    print("工具的执行结果 " + str(output)[:200])
                except Exception as exc:
                    output = f"Error: {exc}"
                    is_error = True
                    print(f"\033[31m[tool] failed: {exc}\033[0m")

                content = str(output)

                # 同参循环检测：仅对成功调用计数，错误重试不算 loop
                if not is_error:
                    sig = _tool_signature(block.name, block.input)
                    count = tool_call_counts.get(sig, 0) + 1
                    tool_call_counts[sig] = count

                    if count >= TOOL_LOOP_HARD_K:
                        # 硬性 kill switch：当前轮工具结果照常回传，但循环结束后 return
                        content += (
                            f"\n\n[system] Tool loop aborted: {block.name} has been "
                            f"called {count} times with identical arguments. "
                            f"Terminating to prevent runaway."
                        )
                        print(
                            f"\033[31m[abort] tool loop detected: {block.name} "
                            f"called {count}x with same args, terminating.\033[0m"
                        )
                        aborted_by_loop = True
                    elif count >= TOOL_LOOP_SOFT_K:
                        # 软提示：把警告塞进 tool_result，由模型自己决策跳出
                        preview = str(output)[:200]
                        content += (
                            f"\n\n[system] You have called {block.name} with the "
                            f"same arguments {count} times. Last result: {preview!r}. "
                            f"Stop repeating — try a different approach, summarize "
                            f"what you have, or finish the task."
                        )
                        print(
                            f"\033[33m[loop-warn] {block.name} called {count}x with "
                            f"same args, injecting soft hint.\033[0m"
                        )

                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                    "is_error": is_error,
                })

        # 将工具执行结果作为用户消息追加到对话历史
        # 这会触发下一次 LLM 调用，让模型基于工具结果继续处理
        messages.append({"role": "user", "content": results})

        # 硬性 kill switch：保证 assistant/user 消息成对，再 return
        if aborted_by_loop:
            return

    # 超出最大循环次数，强制终止以避免失控
    print(f"\033[33m[warn] Agent reached MAX_ITERATIONS ({MAX_ITERATIONS}), terminating.\033[0m")


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
            query = input("\033[36mretry-agent >> \033[0m")
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
