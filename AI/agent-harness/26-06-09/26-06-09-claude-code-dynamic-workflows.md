# Claude Code Dynamic Workflows 学习笔记

> 日期：2026-06-09  
> 主题：Claude Code Dynamic Workflows（动态工作流）

## 证据等级标注规则

整份笔记按 6 档证据等级分类，避免把官方事实、脚本原语、实测避坑和社区说法混在一起。

| 标记 | 含义 |
|---|---|
| 【官方事实】 | 可追溯到 Claude Code 官方 workflows 文档原文 |
| 【脚本原语事实】 | workflow script 中实测可用 / 可观察到的 runtime 脚本能力；不等同于官方公开稳定 API 参考 |
| 【实测现象】 | 在真实运行中观察到的现象；可能受版本、模型、权限、环境影响 |
| 【社区说法】 | 来自社区文章 / X 帖的经验、案例或解释；未全部独立核验 |
| 【教学推测】 | 未经验证的推断，标注以示与事实区分 |

---

## 第 1 章：核心定义

### 1.1 Dynamic Workflows 是什么【官方事实】

> 官方原文：
> A dynamic workflow is a JavaScript script that orchestrates subagents at scale. Claude writes the script for the task you describe, and a runtime executes it in the background while your session stays responsive.

中文理解：

| 英文术语 | 中文解释 |
|---|---|
| Dynamic Workflow（动态工作流） | Claude 写的 JS 脚本，用来大规模编排 subagents |
| JavaScript script | JavaScript 脚本 |
| orchestrates subagents at scale | 大规模编排子代理 |
| Claude writes the script | Claude 为用户描述的任务写脚本 |
| a runtime executes it in the background | runtime 在后台执行脚本 |
| your session stays responsive | 当前 Claude Code 会话保持响应 |

关键事实：

```text
1. 形式：JS 脚本
2. 内容：编排 subagents
3. 写法：Claude 为任务写
4. 执行：runtime 后台执行
5. 效果：主会话保持响应
```

### 1.2 与其他多代理机制的区别【官方事实】

| 机制 | 本质 | 编排权 | 中间结果位置 | 适合规模 |
|---|---|---|---|---|
| Subagents（子代理） | Claude 临时生成的工作者 | Claude 逐轮 | Claude 的上下文窗口 | 每轮几个委派 |
| Skills | Claude 遵循的指令 | Claude 跟随 prompt | Claude 的上下文窗口 | 和 subagents 接近 |
| Agent teams | lead agent 监督 peer sessions | lead agent 逐轮 | 共享任务列表 | 少数长期对等 |
| **Workflows** | **runtime 执行的脚本** | **脚本** | **脚本变量** | **每次运行数十到数百 agents** |

核心差异：

> Workflow 把“计划”从 Claude 上下文移到代码里。

这意味着：

```text
- 主对话上下文压力更小：中间结果留在脚本变量里
- 编排可重复：脚本可读、可保存、可重跑
- 质量模式可编码：对抗验证、评审面板、循环直到无新发现等
```

### 1.3 适用 vs 不适用【官方事实 + 教学推测 + 社区说法】

#### 适合的场景【官方事实】

官方文档给的典型例子：

- codebase-wide bug sweep（全仓库 bug 扫描）
- 500-file migration（500 文件迁移）
- research question with sources cross-checked（多来源交叉核查研究）
- hard plan worth drafting from several independent angles（值得多角度独立起草再比较的困难计划）

#### 常见社区经验场景【社区说法】

社区文章反复提到的模式和场景：

- 大规模代码迁移 / 重构
- 深度研究与带引用报告
- 文档事实核查 / 技术主张核查
- 对抗式验证 / skeptical verifier
- 候选项排序、命名、设计方向筛选
- 工单 triage、backlog 去重、规则合规检查
- 故障排查：多个 agent 提假设，再由 verifier/refuter 面板检验

#### 常用 workflow 模式【社区说法】

| 模式 | 核心做法 | 适合任务 |
|---|---|---|
| 分类后路由 | 先由 classifier 判断任务类型 / 对象类型，再分派给对应 specialist agent | 工单 triage、规则分流、不同文件类型处理 |
| 并行拆分后汇总 | 按文件、模块、章节、候选项或检查维度 fan-out，再由汇总阶段合并 | 大规模迁移、批量审计、文档核查 |
| 对抗式验证 | finder 先提出发现，verifier / refuter 专门尝试反驳 | 安全审计、事实核查、高风险结论确认 |
| 生成后筛选 | 多个 agent 生成候选，再按 rubric 评分、去重、筛选 | 命名、文案、设计方向、prompt 方案 |
| 锦标赛式比较 | 候选两两比较或分组晋级，避免一次性全局排序质量下降 | 大量候选排序、主观方案评审 |
| 循环直到无新发现 | 多轮 finder 持续搜索，连续若干轮没有新结果后停止 | bug sweep、规则违反扫描、资料穷尽式研究 |
| 假设面板 + 反驳 | 多个 agent 基于不同证据提出根因假设，再由 verifier/refuter 检验 | 故障排查、复杂问题诊断 |
| 读取者 / 执行者隔离 | 低权限 agent 读取不可信内容，高权限 agent 只接收清洗后的摘要 | 公开网页、issue、工单、用户提交内容处理 |

这些模式不是官方 checklist，而是社区文章中反复出现的经验抽象。使用时仍应先判断任务是否足够大、可拆分、可验证，避免为小任务引入过高 token 成本。

#### 不适合的场景【教学推测】

- 单文件 / 小改动
- 价值很低、手动完成很快的任务
- 目标模糊到无法拆分、无法验证的任务
- 纯确定性 IO、定时、ETL、业务集成流程

重要边界：

```text
Dynamic Workflows 不是通用工作流引擎。
不能替代 Dify / n8n / Airflow / Temporal。

更精确地说：
- 纯确定性集成 / 调度不适合交给 Dynamic Workflows。
- 但如果任务核心是 AI 判断、研究、分流、验证、归纳，workflow 可以和 /loop、MCP、tools 搭配做周期性或跨系统辅助流程。
```

---

## 第 2 章：可用性、启用条件与运行限制

### 2.1 可用性【官方事实】

官方文档说明：

| 项 | 说明 |
|---|---|
| 阶段 | research preview（研究预览） |
| Claude Code 版本 | v2.1.154 或更高 |
| 计划 | 所有付费计划可用 |
| Provider | Anthropic API，以及 Amazon Bedrock、Google Cloud Vertex AI、Microsoft Foundry |
| Pro | 需要在 `/config` 的 “Dynamic workflows” 行启用 |
| 表面 | CLI、Desktop、IDE 扩展、`claude -p`、Agent SDK 等 |

关闭方式【官方事实】：

```text
- /config 里关闭 “Dynamic workflows”
- ~/.claude/settings.json 设置 "disableWorkflows": true
- 环境变量 CLAUDE_CODE_DISABLE_WORKFLOWS=1
- 组织级可通过 managed settings / Claude Code admin settings 关闭
```

### 2.2 workflow script 可用机制【官方事实 + 脚本原语事实】

| 机制 | 用途 | 证据等级 |
|---|---|---|
| workflow 是 JavaScript script | 编排 subagents | 【官方事实】 |
| 后台 runtime 执行 | 主会话保持响应 | 【官方事实】 |
| `args` | saved workflow 接收输入；脚本通过全局 `args` 读取 | 【官方事实】 |
| `.claude/workflows/` / `~/.claude/workflows/` | 保存复用 workflow | 【官方事实】 |
| `agent()` | 启动 subagent | 【脚本原语事实】 |
| `parallel()` | barrier 型并行：并行执行一组任务，等待全部完成 | 【脚本原语事实】 |
| `pipeline()` | 流水线：每个 item 依次过多个 stage，不必等所有 item 在同一 stage 完成 | 【脚本原语事实】 |
| `phase()` | 标记阶段，供进度视图分组 | 【脚本原语事实】 |
| `log()` | 输出进度日志 | 【脚本原语事实】 |
| `budget` | 脚本级预算对象，可读取 `total` / `spent()` / `remaining()` | 【脚本原语事实】 |

注意：公开官方 workflows 页面没有详细列出 `agent()`、`parallel()`、`pipeline()`、`budget` 的字段表；这些属于 workflow script 中实测可用 / 可观察到的脚本原语，而不是官方页面正文直接给出的稳定 API 参考。

### 2.3 `parallel()` 与 `pipeline()` 的关键区别【脚本原语事实】

| 函数 | 语义 | 适合场景 |
|---|---|---|
| `parallel(thunks)` | barrier：所有 thunk 并行开始，全部返回后继续 | 下一步必须看到所有结果，如全局去重、全局排序、早停判断 |
| `pipeline(items, stage1, stage2, ...)` | 流水线：每个 item 独立穿过各 stage，快的 item 不必等慢的 item | 多文件迁移、逐项审查、发现后立即验证 |

经验规则：

```text
默认优先 pipeline。
只有下一阶段确实需要上一阶段“全部结果”时，才用 parallel 作为 barrier。
```

### 2.4 运行限制【官方事实 + 脚本原语事实】

| 约束 | 说明 | 证据等级 |
|---|---|---|
| 最多 16 个并发 agents | CPU 核心有限时更少 | 【官方事实】 |
| 每次运行最多 1000 agents | 防止失控循环 | 【官方事实】 |
| 无中途用户输入 | 只有代理权限提示可以暂停；阶段间人工签署应拆成多个 workflow | 【官方事实】 |
| 脚本不能直接文件系统 / shell | 读写文件、运行命令由 agent 通过工具完成 | 【官方事实】 |
| 同一 session 内可恢复 | 停止后已完成 agents 用缓存结果，其余继续 | 【官方事实】 |
| 跨 session 不能恢复 | 退出 Claude Code 后，下个 session 从头启动 workflow | 【官方事实】 |
| workflow 脚本不是 Node.js 全能力 | 标准 JS 内建可用，但不能直接用 filesystem / Node API | 【脚本原语事实】 |
| 避免非确定性调用 | 如 `Date.now()`、`Math.random()`、无参 `new Date()` 会破坏可恢复性，runtime 中不可用 | 【脚本原语事实】 |

关于恢复的澄清：

> 如果社区文章说“恢复后继续”，应限定为同一 Claude Code session 内的暂停/恢复；不是退出 Claude Code 后跨 session 续跑。

### 2.5 权限行为【官方事实】

- workflow 生成的 subagents 以 `acceptEdits` 模式运行；文件编辑自动批准。
- subagents 继承当前会话的 tool allowlist。
- Shell command、network fetch、不在 allowlist 的 MCP tools 仍可能在运行中触发权限提示。
- 长时间运行前，应把需要的命令 / MCP 工具加入 allowlist，避免 workflow 中途卡住。
- 在 `claude -p` 和 Agent SDK 中没有交互式确认；工具调用遵循配置的权限规则。

---

## 第 3 章：workflow script 的结构输出：两条路线

### 3.1 `schema` 的定位【脚本原语事实 + 实测现象】

```text
schema 是 workflow runtime 支持的结构化输出机制。
是否使用 schema 是工程取舍：
- schema 路线：更干净、更强约束，但 schema mismatch 可能导致 agent 失败。
- 防御式 JSON 路线：更宽容，但要自己写 tryParseJson / isValidFinding / buildLocalReport。
```

实测中，schema 模式可能因结构化输出不匹配导致 agent 失败；防御式 JSON 路线适合更重视容错与兜底产物的场景。

### 3.2 路线 A：`schema` 结构化输出路线【脚本原语事实】

形态：

```js
const result = await agent('...', {
  label: 'review:item-a',
  phase: 'Review',
  schema: SOME_JSON_SCHEMA,
})
```

特点：

| 优点 | 风险 |
|---|---|
| 返回对象更干净 | subagent 若未按 runtime 期待调用结构化输出，可能失败 |
| runtime 帮忙验证 schema | schema 太复杂或 prompt 不匹配时，失败概率上升 |
| 下游代码可少写解析逻辑 | 对模型 / 运行环境更敏感 |

### 3.3 路线 B：防御式 JSON 路线【实测现象】

核心链路：

```text
agent 返回（可能是字符串）
  → tryParseJson 提取 JSON
  → isValidFinding / isValidVerdict 严格过滤
  → buildLocalReport 本地兜底
```

适用情况：

- schema 模式在当前环境不稳定；
- 希望 agent 失败时不拖垮整个 workflow；
- 可以接受脚本层自己解析和过滤；
- 目标是“尽量返回 useful artifact”，不是“严格 schema 失败即停止”。

### 3.4 `StructuredOutput` 的正确理解【脚本原语事实 + 实测现象】

错误信息可能出现：

```text
Error: agent({schema}): subagent completed without calling
       StructuredOutput (after 2 in-conversation nudges)
```

```text
StructuredOutput 不是用户 prompt 里应该手动要求调用的普通业务工具。
它更像 runtime 在 schema 模式下注入 / 期待的内部结构化输出机制。

使用 schema 时：让 runtime 处理结构化输出，不在业务 prompt 里提 StructuredOutput。
不用 schema 时：prompt 里描述 JSON shape，并用脚本层解析 / 过滤 / 兜底。
```

---

## 第 4 章：防御式 workflow 模式

### 4.1 `tryParseJson`：应对 agent 返回字符串【实测现象】

agent 可能返回：

```text
Here is my analysis:
{
  "id": "item-a",
  "summary": "..."
}
```

直接 `JSON.parse` 整个字符串会失败，因为前面有 prose。防御式写法会先尝试直接 parse，失败后扫描平衡花括号 / 方括号：

```js
function tryParseJson(s) {
  if (s === null || s === undefined) return null
  if (typeof s === 'object') return s
  if (typeof s !== 'string') return null

  try { return JSON.parse(s) } catch (_) {}

  for (let i = 0; i < s.length; i++) {
    const ch = s[i]
    if (ch !== '{' && ch !== '[') continue
    // ...扫描平衡 JSON 块
  }
  return null
}
```

为什么重要：

```text
isValidFinding 只能过滤对象。
如果 agent 返回字符串，直接过滤会全部失败。
tryParseJson 是“字符串 → 对象”的桥。
```

### 4.2 `isValidFinding` / `isValidVerdict`：严格过滤【实测现象】

```js
const SEVERITIES = ['low', 'medium', 'high', 'critical']
const CONFIDENCES = ['low', 'medium', 'high']
const STATUSES = ['confirmed', 'uncertain', 'refuted']

function isValidFinding(f) {
  return !!f
    && typeof f.id === 'string' && f.id.length > 0
    && typeof f.summary === 'string' && f.summary.length > 0
    && typeof f.severity === 'string' && SEVERITIES.includes(f.severity)
    && typeof f.confidence === 'string' && CONFIDENCES.includes(f.confidence)
    && typeof f.rationale === 'string' && f.rationale.length > 0
}
```

关键细节：

```text
1. 枚举值用 const 数组先定义，便于复用。
2. 检查 length > 0，避免空字符串。
3. !!f 兜住 null / undefined / 0 / false。
```

### 4.3 `buildLocalReport`：本地兜底【实测现象】

```js
function buildLocalReport(ann) {
  const confirmed = []
  const uncertain = []
  const refuted = []

  for (const f of ann) {
    if (f.verdict === 'confirmed') confirmed.push(f)
    else if (f.verdict === 'refuted') refuted.push(f)
    else if (f.verdict === 'uncertain') uncertain.push(f)
    else if (f.confidence !== 'high') uncertain.push(f)
  }

  return {
    confirmed,
    uncertain,
    refuted,
    summary: 'Local fallback report assembled from ' + ann.length + ' annotated findings.',
    takeaways: [...],
  }
}

const report = isValidReport(reportParsed)
  ? reportParsed
  : buildLocalReport(annotated)
```

核心思想：

```text
不完全依赖 synthesize agent 给最终结果。
即便 synthesize agent 失败，脚本也能从 annotated findings 拼出 useful artifact。
```

### 4.4 prompt 三件套：TASK / shape / BOUNDARY【实测现象】

防御式 JSON 路线中，prompt 应同时说明任务、返回结构和边界：

```text
TASK:       目标
shape:      返回结构
BOUNDARY:   不要做什么
```

示例：

```text
TASK: <具体目标>
Input item: <inline JSON>
Return ONE JSON object with exactly these fields:
{ id, summary, severity, confidence, rationale }
BOUNDARY:
- Return ONLY the JSON object. No prose, no markdown fences.
- Do not invent file paths, line numbers, or function names.
- Do not add fields beyond the five listed.
```

---

## 第 5 章：实测错误清单

### 5.1 反向证据【实测现象】

| 做法 | 风险 / 后果 | 推荐处理 |
|---|---|---|
| 使用 `schema` 路线 | schema mismatch 可能导致 agent 失败 | 保持 schema 简洁，并让 prompt 与 schema 对齐；若失败容忍度更重要，可改用防御式 JSON 路线 |
| 在业务 prompt 中要求“调用 StructuredOutput 工具” | 可能误导 agent；StructuredOutput 不是用户应指挥的普通业务工具 | 不在业务 prompt 中提 StructuredOutput |
| 告诉 agent “runtime 会校验你的输出” | 可能污染 prompt，引入与任务无关的机制描述 | 只明确业务 shape / boundary |
| 在业务 prompt 中混入 runtime 内部机制描述 | 可能污染 prompt，引入与任务无关的信息 | prompt 只描述任务、返回结构和边界；脚本层负责解析、过滤和兜底 |

### 5.2 错误信息识别【实测现象】

#### 错误 1：`completed without calling StructuredOutput`

```text
Error: agent({schema}): subagent completed without calling
       StructuredOutput (after 2 in-conversation nudges)
```

含义：

```text
这是 schema 路线下的结构化输出失败。
StructuredOutput 不应作为业务 prompt 中手动要求调用的普通工具。
```

可能修复：

```text
1. 简化 schema。
2. 改强 prompt，让输出目标与 schema 更一致。
3. 若失败容忍度更重要，则改走防御式 JSON 路线：不传 schema + tryParseJson + isValidX + fallback。
```

#### 错误 2：findings 为空

含义：

```text
findings 为空 ≠ 一定没发现问题。
可能是 agent 返回字符串 / prose / 非结构化对象，导致过滤失败。
```

修复：

```text
- 加 tryParseJson。
- 强化 Return ONLY JSON 的 prompt。
- 检查 transcript，看 agent 实际返回了什么。
```

#### 错误 3：workflow 整体 fail

原则：

```text
看 transcript，不靠错误信息猜机制。
错误信息真实存在，但官方文档未必解释内部机制。
```

---

## 第 6 章：`agent()` 字段与模型路由

### 6.1 默认模型行为【官方事实】

> 官方原文：
> Every agent in a workflow uses your session's model unless the script routes a stage to a different one.

中文理解：

```text
workflow 里的每个 agent 默认使用当前 session model。
除非脚本把某个阶段 / agent 路由到不同模型。
```

### 6.2 `agent()` 字段【脚本原语事实】

本次最小 workflow 实测通过的写法：

```js
await agent(prompt, {
  label: 'review:item-a',
  phase: 'Review',
  model: 'claude-haiku-4-5',
  schema: SOME_SCHEMA,
})
```

实测结果：

```text
- agent(prompt, { label, phase, schema }) 可返回结构化对象。
- agent(prompt, { label, phase, model }) 可正常返回文本。
```

说明：

```text
官方 workflows 页面说明了 phase 展示和 model 路由概念，
但没有把 label / phase / model / schema 列为稳定公开 API 字段表。
这些字段应按“脚本原语事实”记录，后续以 Claude Code 实际生成脚本和官方文档更新为准。
```

### 6.3 模型路由的工程写法【教学推测】

Claude Code 可能会写类似模型注册表：

```js
const MODEL_REGISTRY = {
  cheap: 'claude-haiku-4-5',
  strong: 'claude-opus-4-8',
}

function MODEL_FOR(key) {
  return MODEL_REGISTRY[key] || MODEL_REGISTRY.strong
}
```

然后在 agent call 中使用：

```js
await agent(prompt, {
  label: 'triage:item-b',
  phase: 'Triage',
  model: MODEL_FOR('cheap'),
})
```

实际是否按预期路由，应在自己的目标环境小规模验证。

---

## 第 7 章：`args`、保存与触发方式

### 7.1 `args`【官方事实】

> A saved workflow can accept input through the args parameter.  
> The script reads it as a global named args.

示例：

```text
> Run /triage-issues on issues 1024, 1025, and 1030
```

要点：

```text
- saved workflow 可通过 args 接收输入。
- 脚本中读取全局变量 args。
- args 可以是问题、路径列表、配置对象等结构化数据。
- 如果省略，args 是 undefined。
```

### 7.2 保存位置【官方事实】

| 位置 | 路径 | 特点 |
|---|---|---|
| 项目级 | `.claude/workflows/` | 随项目共享 |
| 用户级 | `~/.claude/workflows/` | 多项目可用，仅自己可见 |
| 同名优先 | 项目级 | 项目 workflow 覆盖同名用户 workflow |

保存方式：

```text
/workflows 视图 → 选择 run → 按 s → 选择项目级或用户级位置。
```

保存后可作为：

```text
/<name>
```

运行。

### 7.3 触发方式【官方事实】

```text
- /deep-research（内置 workflow）
- prompt 中包含 ultracode 关键字
- 用自然语言明确要求 “use a workflow” / “run a workflow” / “fan out agents”
- /effort ultracode：让 Claude 对每个实质性任务自动规划 workflow
- 已保存 workflow：/<name>
```

补充：

```text
v2.1.160 之前，字面触发关键字是 workflow；自然语言请求在两个版本中都有效。
ultracode 是 xhigh effort + 自动 workflow 编排。
开启 ultracode 后，一个请求可能变成多个连续 workflow：理解 → 修改 → 验证。
```

---

## 第 8 章：用户侧核心能力

### 8.1 判断何时用【官方事实 + 教学推测】

适合：

```text
多文件 / 大规模 / 可并行 / 可验证
价值高、风险可控
复杂任务
需要对抗验证或多角度比较
```

不适合：

```text
单文件 / 小改动
目标模糊、无法拆解
纯确定性集成 / 调度
成本高于收益的小任务
```

### 8.2 写 workflow request 的 8 个要素【教学推测】

| 要素 | 含义 |
|---|---|
| Goal | 我要完成什么 |
| Scope | 检查哪里、不检查哪里 |
| Permission | 只读还是允许修改 |
| Target items | 处理对象 |
| Checks | 检查项 |
| Evidence | 每个发现必须有证据 |
| Verification | 高危要反驳 / 独立验证 |
| Output | 最终报告格式 |

### 8.3 审查 Claude Code 写的 script【教学推测】

重点看 8 处：

```text
1. meta / phases 是否清楚，阶段名是否和实际 phase() 一致。
2. agent() 字段是否符合实测可用写法，如 { label, phase, model, schema }。
3. 如果使用 schema：schema 是否过复杂，prompt 是否与 schema 一致。
4. 如果不用 schema：是否有 tryParseJson。
5. 是否有 isValidFinding / isValidVerdict 等严格过滤。
6. 是否有 buildLocalReport / fallback，避免最终 synthesize 失败导致无产物。
7. prompt 是否有 TASK / shape / BOUNDARY，且不要提 runtime 内部机制。
8. parallel / pipeline 是否选对：需要全局 barrier 才用 parallel，否则优先 pipeline。
```

不要再把“是否有 schema”本身当作错误；应判断它是否适合该任务。

### 8.4 让 verifier 做真正的反驳【实测现象 + 社区说法】

prompt 必须强调：

```text
- TRY TO REFUTE
- Do NOT just agree
- status 三个合法值明确
- 如果 evidence 弱就 refuted / uncertain
```

示例：

```text
TASK: act as an independent verifier. TRY TO REFUTE each finding.
Do NOT just agree.

Return ONE JSON ARRAY; one verdict per input finding.
Each must have exactly these fields:
{ id, status: "confirmed | uncertain | refuted", reason }

BOUNDARY:
- status must be exactly one of the three values.
- If the rationale is weak, return "refuted" or "uncertain".
- Return ONLY the JSON array. No prose, no markdown fences.
```

### 8.5 不可信输入隔离【社区说法 + 安全边界】

社区文章多次提醒：处理公开网页、用户提交、issue、工单等不可信内容时，应隔离：

```text
读取 / 摘要 agent：只读低权限，接触原始不可信内容。
执行 / 修改 agent：高权限，但只接收经过清洗的结构化摘要，不直接接触原始恶意内容。
```

目的：降低 prompt injection 让高权限 agent 执行危险操作的风险。

---

## 第 9 章：社区文章核对结论

### 9.1 可采纳为社区经验的内容【社区说法】

社区文章大体与官方方向一致，以下内容适合保留为社区经验：

- 动态 workflow 把计划移入代码。
- 多 agent 隔离上下文，降低长上下文漂移。
- 适合大规模迁移、审计、研究、事实核查、对抗验证。
- 常见模式包括 fan-out 汇总、对抗验证、生成筛选、锦标赛比较、循环直到无新发现。
- 成本较高，小任务不值得。
- 不可信输入应隔离读取 agent 和高权限执行 agent。
- `/workflows` 可查看进度，按 `s` 保存。
- `ultracode` 和 `/effort ultracode` 是触发方式。

### 9.2 只能标为社区说法 / 未独立核验的内容【社区说法】

以下不要直接写成官方事实：

- Bun 从 Zig 到 Rust 重写使用 Dynamic Workflows 的具体数据。
- Anthropic 内部团队已使用数月。
- 某个案例具体用了多少 agents、多少 tokens、耗时多久。
- “Claude API 支持 workflows”这类笼统表述。更准确说法是 Claude Code surfaces、`claude -p`、Agent SDK；普通 Messages API 不是直接运行 workflow script 的接口。
- “恢复 Claude Code 会话后可继续”如果没有限定同一 session，容易与官方“跨 session 从头启动”冲突。

---

## 第 10 章：关键口诀

### 10.1 三大核心口诀

1. **脚本是本体，代理是工人。**

```text
workflow script 负责调度。
真正读文件、改文件、跑命令的是 subagent。
```

2. **结构输出有两路，按风险选。**

```text
A. schema 路线：
- 使用 agent(prompt, { schema })
- runtime 负责结构化输出约束
- 优点：返回对象更干净
- 风险：schema mismatch 可能导致该 agent 失败

B. 防御式 JSON 路线：
- 不传 schema
- prompt 明确 Return ONLY JSON shape
- 脚本用 tryParseJson 解析
- 再用 isValidFinding / isValidVerdict 过滤
- 最后用 buildLocalReport 兜底
```

3. **高危要反驳，不只确认。**

```text
verifier 的正确 prompt:
"TRY TO REFUTE"
"Do NOT just agree"

错误:
"confirm this finding"
```

### 10.2 辅助口诀

4. **失败要挡，空要识别。**

```text
空 findings ≠ 没发现问题。
可能是 prompt 不够强，也可能是返回格式不合格。
看 transcript，不靠空数组下结论。
```

5. **纯调度不上 workflow，AI 判断才值得。**

```text
如果只是稳定定时、IO、重试、SLA，用工程工作流系统。
如果要研究、验证、分流、归纳、对抗评审，才考虑 Dynamic Workflows。
```

---

## 第 11 章：调试原则

### 11.1 证据等级

使用本笔记时先看标签：

```text
官方事实 > 脚本原语事实 > 实测现象 > 社区说法 > 教学推测
```

错误信息真实存在，但官方文档未必解释内部机制；不要从一次失败推导出永久规则。

### 11.2 排障顺序

```text
1. 先看 /workflows 进度和 agent 详情。
2. 再看 transcript 中 agent 实际返回了什么。
3. 判断是 schema 路线失败，还是防御式 JSON 路线解析 / 过滤失败。
4. 如果 schema 失败：简化 schema、强化 prompt，或改走防御式 JSON。
5. 如果 findings 空：检查 tryParseJson、isValidFinding、prompt shape。
6. 如果 workflow fail：不要猜，读取脚本和 agent 输出。
```

### 11.3 成本与范围

```text
- 大任务先小范围试跑。
- /workflows 视图看每个 agent 的 token 使用。
- 必要时停止运行；已完成结果不会丢失（同 session 内可恢复）。
- 可在 prompt 中要求某些阶段使用较小模型。
- 可用 budget 在脚本中控制后续 agent 调用。
```

---

## 第 12 章：相关资源

### 12.1 官方文档

- Claude Code Dynamic Workflows: https://code.claude.com/docs/zh-CN/workflows
- Claude Code sub-agents: https://code.claude.com/docs/zh-CN/sub-agents
- Claude Code tools-reference: https://code.claude.com/docs/zh-CN/tools-reference

### 12.2 社区文章

- https://x.com/PandaTalk8/status/2063918562318946740
- https://x.com/trq212/status/2061907337154367865
- https://x.com/0xCodez/status/2062127385923776831
- https://x.com/knoYee_/status/2062144250532561370
- https://x.com/AlphaSignalAI/status/2060361091474223504
- https://x.com/so_ainsight/status/2060598271161291042
