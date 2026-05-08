# 技术点：Agent 同参工具循环检测（Soft Hint + Hard Kill）

## 一、要解决的问题

Agent 在 tool-use 循环中陷入"同一工具 + 同一参数"反复调用，token 暴涨、任务永不完成。常见诱因：

- 模型读不懂工具结果
- 目标不可达却不肯放弃
- 被错误信息卡住，反复重试同一个失败操作

## 二、核心思路（两级阈值，一个台阶 + 一道兜底）

**给签名，做计数，分两级处置**：

- **签名**：把每次 `tool_use` 规范化成 `(tool_name, sorted_json(input))` 的字符串。
- **计数**：维护一张 `{签名: 次数}` 的计数表，作用域限定在单次 `agent_loop` 内。
- **软处置（K=3）**：把警告塞进 `tool_result.content` 末尾——"你已用相同参数调用 X N 次，上次结果是 Y，请换思路或结束"——让模型自己读到、自己台阶下来。
- **硬处置（K=5）**：当前轮工具处理完毕、消息成对追加之后，主动 `return`，打印 `[abort] tool loop detected`，兜底防失控。

## 三、四个关键设计决策（最容易被追问的点）

| 决策 | 为什么这么做 |
|------|------|
| **签名用 `json.dumps(sort_keys=True)`** | 字典顺序不影响判定，`{a,b}` 与 `{b,a}` 算同一调用 |
| **计数表放在 `agent_loop` 内部** | 跨任务自动归零，避免上一轮的失败状态污染下一轮 |
| **`is_error=True` 的回合不计数** | 工具瞬时失败时模型用同参数重试是**正确行为**，不能被 loop 检测压制 |
| **硬 abort 不在 `for block` 中间 return** | 必须等本轮所有 `tool_use` 都收到 `tool_result`，assistant/user 消息成对后才 return，否则下次对话历史会被 Anthropic API 判为非法 |

## 四、为什么是 Soft + Hard 两级，而不是直接 Kill

- **直接 kill 太硬**：模型可能下一步本来就要换思路，被切断反而浪费已有上下文。
- **单纯软提示又不够**：遇到顽固模型可能继续打转，token 还是会爆。
- **两级配合**：软提示给模型一次"自我修正"的机会（实测大多数情况下一轮就跳出），硬 kill 是兜底保险，两者覆盖正常和病态两种场景。

## 五、与已有"三层健壮性"的关系

这是第四层防线，补上前三层的盲区：

| 层 | 防什么 | 检测维度 |
|---|---|---|
| `with_retry` | API 瞬时故障（429/500/503） | HTTP 状态码 |
| `MAX_ITERATIONS` | 任意循环失控 | 轮数 |
| 工具异常捕获 | 单工具崩溃 | 异常 |
| **同参 loop 检测** | **模型行为异常** | **调用签名重复度** |

前三层是"基础设施级"防御，这一层是"语义级"防御——专门治"模型本身陷在死胡同里出不来"。

## 六、关键代码骨架

```python
# 签名规范化
def _tool_signature(name: str, tool_input: Any) -> str:
    payload = json.dumps(tool_input, sort_keys=True, default=str, ensure_ascii=False)
    return f"{name}|{payload}"

# 在 agent_loop 内部
tool_call_counts: Dict[str, int] = {}
aborted_by_loop = False

for block in response.content:
    if block.type == "tool_use":
        # ... 执行工具，得到 output / is_error ...
        content = str(output)

        # 仅成功调用计数，错误重试不算 loop
        if not is_error:
            sig = _tool_signature(block.name, block.input)
            count = tool_call_counts.get(sig, 0) + 1
            tool_call_counts[sig] = count

            if count >= TOOL_LOOP_HARD_K:        # K=5
                content += "\n\n[system] Tool loop aborted ..."
                aborted_by_loop = True
            elif count >= TOOL_LOOP_SOFT_K:      # K=3
                content += "\n\n[system] You have called X same args N times ..."

        results.append({"type": "tool_result", ..., "content": content})

messages.append({"role": "user", "content": results})
if aborted_by_loop:                              # 等消息成对后再 return
    return
```

## 七、一句话总结（口头复述用）

> 给每次工具调用算个 `(name + 规范化 input)` 签名，在 `agent_loop` 内部计数。同签名达到 3 次，把软提示塞进 `tool_result` 让模型自我修正；达到 5 次，等当前轮消息成对后强制 return。错误回合不计数，避开和重试机制打架。
