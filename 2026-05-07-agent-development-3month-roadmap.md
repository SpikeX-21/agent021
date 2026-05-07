# Agent 开发 3 个月学习路线（工程化方向）

> 起草日期：2026-05-07
> 学习者画像：Python 入门级，已有基础编程能力，未系统调过 LLM API
> 时间预算：10-12 小时/周 × 12 周 ≈ 130 小时
> 目标：达到**工程化/生产级** Agent 开发能力 —— 关注上下文工程、记忆管理、工具系统、评估、可观测性、成本治理
> 主线项目：研究助手 Agent（v1 → v6）
> 加餐项目：迷你代码 Agent（v1 → v2）

---

## 0. 总览

### 0.1 整体节奏（三阶段）

| 阶段 | 周次 | 主题 | 产出 |
|---|---|---|---|
| **地基期** | W1-W2 | LLM API、Prompt、Function Calling 基础 | 跑通的 ReAct demo（裸写） |
| **主线推进期** | W3-W10 | 工具系统 → RAG → 上下文工程 → 记忆 → 多步规划 → 评估 → 代码 Agent | 研究助手 v1-v6 + 代码 Agent v1-v2 |
| **生产化收尾期** | W11-W12 | 可观测性、成本治理、部署 | 上线 demo + 评估报告 + 架构文档 |

### 0.2 双线机制（W3 起每周）

- **项目线（6-8 小时）**：推进贯穿项目，新增本周能力，跑通并打 tag
- **理论线（4-5 小时）**：固定"理论日"（建议周末），精读 1 篇 + 泛读 1-2 篇 + 独立小练习（单独 notebook，不进项目）

> **铁律**：理论笔记不写完不动项目代码，防止理论被挤掉。

### 0.3 核心原则

1. **能裸写就先裸写**：理解原理后再引入框架。ReAct 循环、工具调度、记忆系统都要手写一遍才能上框架。
2. **每主题对照"造轮子 vs 用库"**：写一份对比文档贯穿全程。
3. **预算硬上限**：每月 API ≤ $20。强制学习 prompt caching、模型分级、成本分析。
4. **评估先行**：W8 建评测集后，每次迭代都要跑评估，不看体感看数字。

---

## 1. 技术栈选型

| 类别 | 选型 | 备注 |
|---|---|---|
| 语言/环境 | Python 3.11+，uv（包管理），Jupyter | uv 安装快 |
| 主 LLM | Anthropic Claude Sonnet 4.6 | 工具调用稳定 |
| 备用 LLM | OpenAI GPT-4o / Claude Haiku | Haiku 跑评估省钱 |
| Agent 框架 | **W1-W6 裸写**，W7 起引入 LangGraph | 先理解再用框架 |
| RAG 组件 | LlamaIndex（loader）+ Chroma（向量库）+ BM25 | 本地化无依赖 |
| 搜索工具 | Tavily API（免费额度）/ SerpAPI | 研究助手核心 |
| 文档解析 | pypdf、trafilatura、BeautifulSoup | 网页 + PDF |
| 代码解析 | tree-sitter、ripgrep | 代码 Agent 专用 |
| 记忆层 | 自写（W6）→ 对比 mem0/Letta | 手写一次再看库 |
| 评估 | promptfoo + 自写 LLM-as-Judge | 轻量可脚本化 |
| 可观测性 | Langfuse（自部署）或 LangSmith | 看 trace/token/延迟 |
| 部署 | FastAPI + Docker + Fly.io/Render | 免费层足够 |
| 版本管理 | Git + 每周打 tag（v1、v2…） | 方便回看迭代 |

---

## 2. 12 周详细路线

### 地基期

#### W1 —— LLM API 与 Prompt 基础

**项目主线（6h）**
- 配置 Anthropic + OpenAI SDK，跑通第一个对话调用
- 写一个命令行问答机器人（`python chat.py`）：多轮对话、system prompt、流式输出
- 输出：`bot-cli/` 初版

**理论线（4h）**
- 精读：Anthropic *Prompt engineering* 总览
- 泛读：OpenAI Prompt 指南
- 主题：角色设定、few-shot、结构化输出、temperature/top_p
- 小练习：同一问题写 5 种 prompt，记录效果差异 → `notebooks/w1_prompt_variants.ipynb`

**交付**：`bot-cli/` + W1 笔记

---

#### W2 —— 手写 ReAct 循环

**项目主线（7h）**
- 实现 ReAct 主循环（不用任何 Agent 框架）：
  - 状态机：`thinking → tool_call → observation → thinking → final_answer`
  - 工具：1 个 `web_search`（Tavily）
  - 手动解析 `tool_use` block，手动拼 `tool_result` 回发
- 加入 max_iteration、超时保护
- 输出：`research-agent/` v0（ReAct 单工具版）

**理论线（4h）**
- 精读：Anthropic *Tool use* 文档（重点：tool_choice、并行工具调用、stop_reason）
- 泛读：ReAct 原论文（Yao et al. 2022）
- 小练习：把你写的 ReAct 循环画成状态图（Mermaid），提交到 notes → `notebooks/w2_react_state_diagram.md`

**交付**：`research-agent` tag `v0-react` + 状态图

---

### 主线推进期

#### W3 —— 工具系统设计（研究助手 v1）

**项目主线（7h）**
- 在 v0 基础上扩展工具集：
  - `web_search`（已有）
  - `arxiv_search`（arXiv API）
  - `fetch_url`（trafilatura 抓正文）
  - `read_pdf`（pypdf）
- 工具层抽象：统一的 `Tool` 基类 + JSON Schema 自动生成 + 参数校验（pydantic）+ 错误返回格式标准化
- 给每个工具写单元测试 + 错误分支测试（URL 404、PDF 损坏等）

**理论线（4h）**
- 精读：Anthropic *Building effective agents*
- 泛读：Toolformer 论文
- 主题：工具粒度设计、幂等性、错误可恢复、描述写法（模型读的是 description）
- 小练习：给 Anthropic blog post 里的"bad vs good tool description"例子做对比笔记

**交付**：`research-agent v1` + 工具测试套件

---

#### W4 —— RAG 基础（研究助手 v2）

**项目主线（7h）**
- 搭本地 RAG：
  - 抓回的网页/PDF 自动 chunk → embedding → Chroma
  - 新工具 `search_my_notes`（BM25 + 向量混合检索）
  - 引用机制：返回结果带 source + chunk_id
- 研究助手能做"先搜网 → 存库 → 后续问答优先查库"

**理论线（4h）**
- 精读：LlamaIndex RAG concepts
- 泛读：*Lost in the Middle* 论文
- 主题：chunk size vs 重叠、embedding 模型选型、hybrid search、rerank
- 小练习：同一文档用 3 种 chunk size（256/512/1024）+ 2 种 overlap，对比 10 个问题的召回 Top-5 命中率 → `notebooks/w4_chunking_ablation.ipynb`

**交付**：`research-agent v2` + chunking 消融报告

---

#### W5 —— 上下文工程（研究助手 v3）

**项目主线（8h）**
- 实现"上下文预算管理器"：
  - 统计当前消息历史 token 数
  - 超阈值触发：旧工具结果摘要化、长观察结果只保留关键段落、引用而非全文回塞
  - 工具结果分级：摘要版 + 完整版可按需再取（通过 `expand_observation(id)` 工具）
- 接入 Anthropic prompt caching：system prompt + 工具定义走 ephemeral cache
- 对比 v2：看 token 消耗降幅

**理论线（4h）**
- 精读：Anthropic *Context engineering* 指南 + *Prompt caching* 文档
- 泛读：Claude long context tips、RAG vs Long Context 综述
- 主题：压缩 vs 摘要 vs 引用、context editing、cache hit rate、上下文腐烂
- 小练习：给 v2 的某个典型会话做 token 分布可视化（bar chart），标出哪部分能压缩 → `notebooks/w5_token_profile.ipynb`

**交付**：`research-agent v3` + token 对比报告（v2 vs v3）

---

#### W6 —— 记忆管理（研究助手 v4）

**项目主线（8h）**
- 实现三层记忆：
  - **短期**：当前对话窗口（已有）
  - **中期（工作记忆）**：本次研究任务的临时笔记，任务结束可持久化
  - **长期**：用户画像（研究领域、偏好引用格式）+ 历史研究主题索引
- 写入触发规则：显式命令（"记住 X"）+ 隐式提取（每轮结束后 LLM 判断是否值得存）
- 检索：对话启动时按当前主题检索长期记忆注入 system prompt
- 遗忘：长期记忆过期机制 + 冲突合并

**理论线（4h）**
- 精读：mem0 设计文档 + Letta README
- 泛读：MemGPT 论文
- 主题：记忆分类、写入触发策略、检索策略、遗忘机制、"Why：为什么这条要记"
- 小练习：给你自己的 v4 写一份"记忆触发规则"文档（什么该记、什么不该记）→ `notes/w6_memory_policy.md`

**交付**：`research-agent v4` + 记忆策略文档

---

#### W7 —— 多步规划 + LangGraph（研究助手 v5）

**项目主线（8h）**
- 从单步 ReAct 升级为"Plan → Execute → Reflect"：
  - Planner 节点：拆解问题为 3-5 步子目标
  - Executor 节点：每步调工具完成
  - Reflector 节点：检查是否达标，不达标回 Planner 调整
- 用 LangGraph 重写主循环：State/Node/Edge 显式建模
- 保留 W2 的裸写版本作为对照，写"裸写 vs LangGraph"笔记

**理论线（4h）**
- 精读：Lilian Weng *LLM Powered Autonomous Agents*
- 泛读：Reflexion、ReWOO、Plan-and-Solve 论文
- 主题：规划 vs 反应、反思机制、LangGraph 的 state/checkpoint
- 小练习：画两版架构图对比（裸 ReAct vs LangGraph Plan-Execute）→ `notes/w7_arch_compare.md`

**交付**：`research-agent v5` + 架构对比文档

---

#### W8 —— Agent 评估（研究助手 v6）

**项目主线（8h）**
- 建一个 20 题的研究问答评测集，4 类各 5 题：
  - 简单事实（单次搜索可答）
  - 多跳推理（需多工具配合）
  - 工具失败恢复（故意给坏 URL）
  - 超长上下文（PDF 超过 50 页）
- 评估维度：
  - 最终答案正确性（LLM-as-Judge，给 rubric）
  - 轨迹合理性（是否调对工具、有无冗余调用）
  - 成本（token + $）
  - 延迟（p50/p95）
- 跑 v3/v4/v5 对比，出评估报告

**理论线（4h）**
- 精读：*Agent-as-a-Judge* 论文
- 泛读：promptfoo 文档、Anthropic evals 指南
- 主题：离线 vs 在线评估、rubric 设计、评估偏差、可重复性
- 小练习：给评测集 20 题写 rubric → `evals/research/rubric.md`

**交付**：`research-agent v6` + `evals/research/` 评测集 + 评估报告

---

#### W9 —— 代码 Agent v1 启动

**项目主线（7h）**
- 新建 `code-agent/`，复用 research-agent 的工具/记忆/上下文基础设施（封装成 `agent-core/` 共享库）
- 新增工具：
  - `read_file(path, start_line, end_line)`
  - `grep(pattern, path)`（封装 ripgrep）
  - `ast_search(symbol_name)`（tree-sitter 查函数/类定义）
  - `list_dir(path)`
- 目标：针对一个小型开源 Python 仓库（推荐：自己过去做的项目或 requests 这类中等规模库）回答问题
  - "函数 X 在哪里定义？谁调用它？"
  - "这个模块的测试覆盖了哪些边界？"

**理论线（4h）**
- 精读：Sweep、Aider、Cursor 架构博客（任选 2 篇）
- 泛读：tree-sitter 官方教程
- 主题：代码 chunking（按函数/类 vs 按行数）、AST 切片、长文件裁剪
- 小练习：同一个问题用"塞整文件"vs"AST 切片"两种方式，对比答案质量 → `notebooks/w9_code_context.ipynb`

**交付**：`code-agent v1` + `agent-core/` 共享库

---

#### W10 —— 代码 Agent v2（可靠性 + 评估）

**项目主线（8h）**
- "先定位再回答"两阶段流程：
  - Phase 1：轻量扫描（grep + ast_search）定位候选文件
  - Phase 2：精读候选文件的相关片段后作答
- 可靠性加固：
  - 工具超时
  - 工具失败重试（带退避）
  - 死循环检测（同一工具参数 >3 次报错）
- 建一个 15 题代码评测集（定位类 + 解释类 + 修改建议类）

**理论线（4h）**
- 精读：Anthropic *Computer use* / 工具失败处理相关文档
- 主题：重试策略、超时、幂等、死循环检测
- 小练习：故意注入工具失败（wrap 一层随机失败），跑评测集看 Agent 的恢复率 → `notebooks/w10_failure_injection.ipynb`

**交付**：`code-agent v2` + `evals/code/` 评测集 + 失败注入报告

---

### 生产化收尾期

#### W11 —— 可观测性 + 成本治理

**项目主线（8h）**
- 接入 Langfuse（推荐自部署，Docker 一把起）或 LangSmith
- 为两个 Agent 加 trace：完整调用链、每步 token、延迟、成本
- 搭一个简易 dashboard：
  - 日 token/费用曲线
  - 工具调用次数 Top-N
  - p50/p95 延迟
  - 失败率
- 启用 prompt caching 后对比降本幅度（量化）

**理论线（4h）**
- 精读：Langfuse 文档 + OpenTelemetry for LLM
- 泛读：LLM FinOps 相关博客
- 小练习：写一份《两个 Agent 的可观测性报告》→ `reports/w11_observability.md`

**交付**：可观测性接入 + 成本分析报告

---

#### W12 —— 部署 + 收尾

**项目主线（8h）**
- FastAPI 包装两个 Agent 为 HTTP 服务（streaming 支持）
- Dockerfile + docker-compose（带 Chroma + Langfuse）
- 部署到 Fly.io 或 Render（免费层）
- 写最终 README：
  - 架构图
  - 快速开始
  - 评估结果
  - 成本分析
  - 已知限制
- 录 15 分钟 demo 视频
- （可选）写 1-2 篇技术博客：如"我手写了一遍 ReAct，再切 LangGraph 发现了什么"

**理论线（3h）**
- 回顾 12 周笔记，完成《造轮子 vs 框架》对比总文档 → `notes/final_build_vs_buy.md`

**交付**：上线 URL + demo 视频 + 完整 README + 总结博客

---

## 3. 理论资源清单

### 3.1 核心文档（长期查）

- Anthropic Docs：*Prompt engineering*、*Tool use*、*Building effective agents*、*Context engineering*、*Prompt caching*、*Computer use*
- OpenAI Cookbook：*Function calling*、*Agents*
- LangGraph 官方教程
- Lilian Weng 博客：*LLM Powered Autonomous Agents*
- LlamaIndex *RAG concepts*

### 3.2 每周精读（1 篇必读）+ 泛读（1-2 篇）

| 周 | 精读 | 泛读 |
|---|---|---|
| W1 | Anthropic Prompt engineering 总览 | OpenAI Prompt 指南 |
| W2 | Anthropic Tool use 文档 | ReAct 原论文 |
| W3 | Anthropic *Building effective agents* | Toolformer |
| W4 | LlamaIndex RAG concepts | *Lost in the Middle* |
| W5 | Anthropic *Context engineering* + Prompt caching | Claude long context tips |
| W6 | mem0 / Letta 设计文档 | MemGPT 论文 |
| W7 | Lilian Weng *LLM Agents* | Reflexion / ReWOO |
| W8 | *Agent-as-a-Judge* 论文 | promptfoo 文档 |
| W9 | Sweep / Aider 架构博客 | tree-sitter 教程 |
| W10 | Anthropic Computer use / 失败处理 | — |
| W11 | Langfuse / LangSmith 文档 | LLM FinOps 博客 |
| W12 | — | 自己写收尾博客 |

---

## 4. 交付物清单

### 4.1 代码仓库

- `research-agent/` —— 6 个版本 tag（v1-v6）
- `code-agent/` —— 2 个版本 tag（v1-v2）
- `agent-core/` —— 共享基础设施库（工具、记忆、上下文预算）
- `notebooks/` —— 12 个理论小练习
- `evals/` —— 两套评测集 + 脚本

### 4.2 文档

- 12 周学习笔记（每周一篇 markdown）
- 两份评估报告（research / code）
- 《造轮子 vs 框架》对比文档
- 可观测性 + 成本分析报告
- 最终架构 README + 部署文档

### 4.3 展示物

- 部署上线的 demo URL（两个 Agent）
- 15 分钟录屏
- 1-2 篇技术博客（可选但强烈建议）

---

## 5. 风险与应对

| 风险 | 应对 |
|---|---|
| 入门起点 + 工程化目标，前 4 周吃力 | W1-W2 严禁上框架；允许"先用后懂"，周末回填理解 |
| API 成本失控 | 月上限 $20；W5 起全量 prompt caching；评估用 Haiku，主流程 Sonnet |
| 理论被项目挤掉 | 固定"理论日"；理论笔记不写完不动项目代码 |
| LangGraph 引入过早导致黑盒 | W7 才引入，且必须对比裸写版本 |
| 评测集质量差，评估无意义 | W8 专门花 4 小时做评测集；4 类题型各 5 题覆盖 |
| 记忆系统设计过度 | W6 先实现三层最小版；对比 mem0 时只借鉴不重写 |
| 部署卡壳占用 W12 | W11 最后一天先做"本地 Docker 化"预演，W12 只负责上云 |

---

## 6. 日常节奏建议

**周一至周五（每天 1-1.5 小时）**
- 工作日聚焦项目主线编码
- 遇阻塞先记 TODO，不深挖，留到理论日

**周六（理论日，3-4 小时）**
- 上午 2 小时：精读 + 笔记
- 下午 1-2 小时：独立小练习 notebook

**周日（收尾日，2-3 小时）**
- 跑通本周项目里程碑
- 打 tag、写周报（本周学到什么 / 踩的坑 / 下周计划）
- 提交所有代码和笔记

---

## 7. 开始前的准备清单

- [ ] 安装 Python 3.11+、uv、VS Code（或 PyCharm）
- [ ] 注册 Anthropic API、OpenAI API、Tavily 搜索 API
- [ ] 配置 `.env` 管理密钥（`python-dotenv`）
- [ ] 新建 GitHub 仓库 `agent-learning-3month`，结构：
  ```
  ├── research-agent/
  ├── code-agent/
  ├── agent-core/
  ├── notebooks/
  ├── evals/
  ├── notes/
  ├── reports/
  └── README.md
  ```
- [ ] 设置 API 预算告警（Anthropic console 可设）
- [ ] 准备好一个记录笔记的工具（Obsidian / Notion / 纯 markdown 都行）

---

**启程。** 每周一个小版本，三个月后你会有一套完整的、可展示的、带评估数据的 Agent 系统 —— 以及真正理解它为什么这样工作。
