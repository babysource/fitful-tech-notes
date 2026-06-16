# OKF（Open Knowledge Format）学习笔记

日期：2026-06-16  
主题：OKF 官方规范、Agent 生成知识包、校验与可视化工程实践

---

## 1. 学习定位

本次学习围绕 OKF v0.1 官方规范展开，目标不是记住零散字段，而是建立一套可迁移的理解框架：

1. OKF 是什么，不是什么。
2. 官方术语如何准确理解。
3. `Knowledge Bundle`、`Concept`、`Frontmatter`、`Link`、`Citation` 如何协同构成知识表示。
4. OKF v0.1 的合规性要求到底有哪些。
5. AI/Agent 如何基于 OKF 生成知识包。
6. 校验脚本和可视化脚本在工程实践中扮演什么角色。
7. 如何区分官方协议、官方参考实现和项目增强工具。

---

## 2. OKF 的官方定位

OKF 全称是 `Open Knowledge Format`。

官方对 OKF 的定位可以概括为：

> OKF 是一种开放的、对人类和 Agent 友好的知识表示格式，用于表示围绕数据和系统的元数据、上下文和经过整理的洞察。

官方强调 OKF 的形态非常小：

```text
a directory of markdown files with YAML frontmatter
```

中文理解：

> OKF 本质上是一个由 Markdown 文件组成的目录树，每个概念文档顶部带有 YAML 元数据块。

因此，OKF 不是数据库、不是查询引擎、不是知识图谱系统，也不是某个工具链本身。它首先是一种文件格式和组织约定。

---

## 3. OKF 的设计目标

OKF 选择 Markdown、YAML frontmatter 和目录树，是为了让知识具备以下特性：

| 特性 | 中文解释 |
|---|---|
| Readable | 人类不依赖专门工具也能阅读 |
| Parseable | Agent 不依赖专用 SDK 也能解析 |
| Diffable | 可以在 Git 等版本控制系统中比较差异 |
| Portable | 可以跨工具、组织和时间迁移 |

这说明 OKF 的核心价值是：

> 用少量结构约定，让知识可读、可解析、可比较、可迁移。

---

## 4. OKF 的官方目标与非目标

### 4.1 官方目标

官方 SPEC 中的目标包括：

1. 定义一种 `enrichment agents` 可以写入的通用格式。
2. 指导 `consumption agents` 如何读取和遍历知识。
3. 促进知识在系统和组织之间交换。
4. 标准化少量必须存在的字段，使内容可以被有意义地消费。

两个角色需要特别记住：

| 官方术语 | 中文理解 |
|---|---|
| `enrichment agents` | 生成、补充、整理知识的 Agent |
| `consumption agents` | 读取、遍历、消费知识的 Agent |

这也是 OKF 适合 AI/Agent 场景的原因。

### 4.2 官方非目标

OKF 官方明确说明它不做以下事情：

1. **不定义固定的 concept type 分类体系。**
   - OKF 要求有 `type` 字段，但没有中央类型注册表。
   - `type` 值由 producer 选择，consumer 必须优雅处理未知类型。

2. **不规定存储、服务或查询基础设施。**
   - OKF 不是向量数据库。
   - OKF 不是图数据库。
   - OKF 不是查询引擎。

3. **不替代领域专用 schema。**
   - OKF 可以引用 OpenAPI、Protobuf、Avro、数据库 schema。
   - OKF 不吞并这些领域格式。

---

## 5. 核心术语

### 5.1 `Knowledge Bundle`（知识包）

官方定义：

> 一个自包含的、层级化的知识文档集合，是 OKF 的分发单位。

关键词：

- self-contained：自包含；
- hierarchical：层级化；
- collection of knowledge documents：知识文档集合；
- unit of distribution：分发单位。

中文理解：

> `Knowledge Bundle` 是 OKF 用来分发、交换和复用知识的基本封装。

### 5.2 `Concept`（概念）

官方定义：

> Bundle 内的单个知识单元，由一个 Markdown document 表示。

Concept 可以描述：

- 具体资产，例如表、API；
- 抽象知识，例如指标、业务流程、操作手册；
- 介于二者之间的任何知识对象。

### 5.3 `Concept ID`

官方定义：

> Concept 文件在 bundle 内的路径，去掉 `.md` 后缀。

例如：

```text
tables/users.md
```

对应：

```text
tables/users
```

因此，`Concept ID` 不是 frontmatter 中手写的字段，而是由文件路径派生出来的。

### 5.4 `Frontmatter`

`Frontmatter` 是 Markdown 文件顶部由 `---` 包围的 YAML 元数据块。

示例：

```yaml
---
type: BigQuery Table
title: Customer Orders
description: One row per completed customer order across all channels.
tags: [sales, orders, revenue]
---
```

### 5.5 `Body`

`Body` 是 frontmatter 之后的 Markdown 正文。

### 5.6 `Link`

`Link` 是从一个 concept 指向另一个 concept 的标准 Markdown 链接，用来表达超出目录父子层级之外的关系。

### 5.7 `Citation`

`Citation` 是从 concept 指向外部来源的链接，用来支持正文中的声明。

---

## 6. Bundle 结构

官方示例结构：

```text
path/to/bundle/
├── index.md
├── log.md
├── <concept>.md
└── <subdirectory>/
    ├── index.md
    ├── <concept>.md
    └── <subdirectory>/
        └── …
```

Bundle 可以被分发为：

- Git repository，官方推荐；
- tarball；
- zip archive；
- larger repository 中的 subdirectory。

### 6.1 保留文件名

OKF 保留两个文件名：

| 文件名 | 作用 |
|---|---|
| `index.md` | Directory listing，用于目录索引和 progressive disclosure |
| `log.md` | Update history，用于记录更新历史 |

官方规则：

```text
index.md 和 log.md 在任意层级都有定义好的含义，不能作为 concept document。
其他 .md 文件都是 concept documents。
```

---

## 7. Concept Document 结构

每个 concept document 是 UTF-8 Markdown 文件，由两部分组成：

1. YAML frontmatter；
2. Markdown body。

官方 frontmatter 模板：

```yaml
---
type: <Type name>                  # REQUIRED
title: <Optional display name>
description: <Optional one-line summary>
resource: <Optional canonical URI for the underlying asset>
tags: [<tag>, <tag>, …]            # Optional
timestamp: <ISO 8601 datetime>     # Optional last-modified time
# … other producer-defined key/value pairs
---
```

字段要求：

| 字段 | 官方性质 | 说明 |
|---|---|---|
| `type` | 必需 | 标识 concept 种类 |
| `title` | 推荐 | 人类可读展示名 |
| `description` | 推荐 | 一句话摘要，用于索引、搜索片段和预览 |
| `resource` | 推荐 | 底层资产的 canonical URI |
| `tags` | 推荐 | 用于横向分类的短字符串列表 |
| `timestamp` | 推荐 | 最后一次有意义修改的 ISO 8601 时间 |

关键点：

> OKF v0.1 的 hard conformance 只要求 `type` 必须非空；其他字段是推荐，不是合规硬要求。

---

## 8. `type` 的准确理解

`type` 是 OKF 中最重要的字段之一。

官方定义：

> `type` 是一个短字符串，用于识别 concept 的种类。Consumer 可以用它做路由、过滤和展示。

官方示例包括：

```text
BigQuery Table
BigQuery Dataset
API Endpoint
Metric
Playbook
Reference
```

但这些只是示例，不是封闭枚举。

准确理解：

```text
type 字段必需；
type 值没有官方中央注册表；
producer 应选择描述性、自解释的 type；
consumer 必须优雅处理未知 type。
```

---

## 9. 官方示例

### 9.1 绑定具体资源的 Concept

官方示例：

```markdown
---
type: BigQuery Table
title: Customer Orders
description: One row per completed customer order across all channels.
resource: https://console.cloud.google.com/bigquery?p=acme&d=sales&t=orders
tags: [sales, orders, revenue]
timestamp: 2026-05-28T14:30:00Z
---

# Schema

| Column        | Type      | Description                              |
|---------------|-----------|------------------------------------------|
| `order_id`    | STRING    | Globally unique order identifier.        |
| `customer_id` | STRING    | Foreign key into [customers](/tables/customers.md). |
| `total_usd`   | NUMERIC   | Order total in US dollars.               |
| `placed_at`   | TIMESTAMP | When the customer submitted the order.   |

# Joins

Joined with [customers](/tables/customers.md) on `customer_id`.

# Citations

[1] [BigQuery table schema](https://console.cloud.google.com/bigquery?p=acme&d=sales&t=orders)
```

该例说明：

- concept 可以绑定底层资源；
- `resource` 表示该资源的 canonical URI；
- `# Schema` 是约定章节；
- Markdown link 表达 concept 之间的关系；
- `# Citations` 支持正文中的声明。

### 9.2 不绑定具体资源的 Concept

官方示例：

```markdown
---
type: Playbook
title: Incident response — data freshness alert
description: Steps to triage a freshness alert on the orders pipeline.
tags: [oncall, incident]
timestamp: 2026-04-12T09:00:00Z
---

# Trigger

A freshness alert fires when `orders` lags more than 30 minutes behind
its expected SLA. See the [orders table](/tables/orders.md).

# Steps

1. Check the [ingestion job dashboard](https://example.com/dash).
2. …
```

该例说明：

- concept 不一定绑定 `resource`；
- 操作流程、业务规则、排障手册也可以是 concept；
- `Playbook` 是描述性 type。

---

## 10. Body 的写法

官方说 body 是标准 Markdown。

Producer 应优先使用结构化 Markdown：

- headings；
- lists；
- tables；
- fenced code blocks。

原因是结构化 Markdown 同时有利于：

- 人类阅读；
- Agent 检索；
- 工具解析。

官方说明：

> Body 没有必需章节。

但有一些约定章节：

| Heading | 用途 |
|---|---|
| `# Schema` | 描述字段、列、结构 |
| `# Examples` | 展示具体示例 |
| `# Citations` | 列出支持正文 claim 的来源 |

---

## 11. Cross-linking

OKF 支持 concept 之间使用标准 Markdown links。

### 11.1 推荐形式：bundle-relative absolute links

以 `/` 开头，相对于 bundle root 解析。

官方示例：

```markdown
See the [customers table](/tables/customers.md) for the join key.
```

官方推荐这种形式，因为当文档在子目录中移动时更稳定。

### 11.2 Relative links

也支持标准相对路径：

```markdown
See the [neighboring concept](./other.md).
```

### 11.3 Link semantics

从 concept A 到 concept B 的 link 表示一种 relationship。

但具体关系类型，例如 parent/child、references、joins-with、depends-on，不是由 link 本身表达，而是由周围文字说明。

Graph view 通常把所有 links 视为：

```text
directed untyped edges
```

中文理解：

> OKF link 通常是有方向、无显式类型的关系边。

### 11.4 Broken links

官方明确：

```text
Consumers MUST tolerate broken links.
```

也就是说，某个 link 指向的目标不存在时，这个 bundle 也不算 malformed。

这是 OKF 宽容消费模型的一部分。

---

## 12. Index Files

`index.md` 可以出现在任意目录，包括 bundle root。

它的作用是：

> 枚举当前目录内容，支持 progressive disclosure。

中文理解：

> `index.md` 让人或 Agent 在打开具体文档前，先知道目录中有什么。

官方示例：

```markdown
# Section / Group Heading

* [Title 1](relative-url-1) - short description of item 1
* [Title 2](relative-url-2) - short description of item 2

# Another Section

* [Subdirectory](subdir/) - short description of the subdirectory
```

关键点：

- `index.md` 通常不含 frontmatter；
- bundle root 的 `index.md` 可以包含 `okf_version: "0.1"`；
- index 条目推荐包含 linked concept 的 `description`；
- producer 可以自动生成 index；
- consumer 可以在缺少 index 时动态合成。

---

## 13. Log Files

`log.md` 可以出现在任意层级，用于记录该 scope 的更新历史。

官方格式：

```markdown
# Directory Update Log

## 2026-05-22
* **Update**: Added new BigQuery table reference for [Customer Metrics](/tables/customer-metrics.md).
* **Creation**: Established the [Dataplex Playbook](/playbooks/dataplex.md).

## 2026-05-15
* **Initialization**: Created foundational directory structure.
* **Update**: Added progressive-disclosure guidelines to the root [index](/index.md).
```

关键点：

- 日期 heading 必须使用 `YYYY-MM-DD`；
- entries 是 prose；
- `**Update**`、`**Creation**`、`**Deprecation**` 是约定，不是强制要求；
- log 推荐 newest first。

---

## 14. Citations

官方说：

> 当 concept body 中的 claim 来自外部材料时，这些来源应该列在文档底部的 `# Citations` 下，并编号。

官方示例：

```markdown
# Citations

[1] [BigQuery public dataset announcement](https://cloud.google.com/blog/products/data-analytics/...)
[2] [Internal data quality runbook](https://wiki.acme.internal/data/quality)
```

Citation links 可以是：

- absolute URLs；
- bundle-relative paths；
- `references/` 子目录中的路径。

核心理解：

```text
Citation 用于支撑正文中的 claim。
```

因此，良好的 producer discipline 包括：

- 未读取的外部链接不能当成已知事实；
- 未分析的图片内容不能被推断；
- 重要 claim 应保留证据来源。

---

## 15. OKF Conformance

这是今天最重要的规范点。

官方定义：一个 bundle 符合 OKF v0.1，如果：

1. 每个非保留 `.md` 文件都有可解析的 YAML frontmatter；
2. 每个 frontmatter 都包含非空 `type` 字段；
3. `index.md` 和 `log.md` 在出现时遵循官方对应结构。

可以压缩为：

```text
OKF v0.1 hard conformance =
  非保留 .md 有可解析 YAML frontmatter
  frontmatter 有非空 type
  reserved files 出现时结构正确
```

官方还强调：

```text
Consumers SHOULD treat all other constraints as soft guidance.
```

Consumer 不能因为以下情况拒绝 bundle：

- 缺少 optional frontmatter fields；
- 未知 `type`；
- 未知额外 frontmatter key；
- broken cross-links；
- 缺少 `index.md`。

这叫 OKF 的 permissive consumption model。

中文理解：

> OKF 的消费方应该宽容，因为 bundle 可能处于增长、重构、部分生成的状态。

---

## 16. Versioning

当前官方 SPEC 是：

```text
OKF version 0.1
```

Bundle 可以在 root `index.md` 中声明：

```yaml
---
okf_version: "0.1"
---
```

如果 consumer 不理解某个版本，也应该尽力消费，而不是直接拒绝。

---

## 17. OKF 与其他格式的关系

官方说 OKF 接近：

- LLM “wiki” repositories；
- Obsidian、Notion 等个人知识工具；
- metadata as code。

但 OKF 的区别是：

> OKF 是被明确规范化的。它固定了互操作需要的少量规则，但不指定工具。

中文理解：

> OKF 与 Obsidian 等工具都可能使用 Markdown，但 OKF 的重点是跨工具、跨组织、面向 Agent 的互操作规范。

---

## 18. AI/Agent 如何生成 OKF

官方说 OKF 设计为：

- authored by people；
- generated by agents；
- exchanged across organizations；
- consumed by both。

中文理解：

> OKF 既可以由人编写，也可以由 Agent 生成；既可以跨组织交换，也可以被人和 Agent 共同消费。

合理的 Agent 生成流程是：

```text
用户提供源资料和目标
  ↓
Agent 读取 OKF SPEC
  ↓
Agent 分析源资料结构
  ↓
Agent 自动制定 producer plan
  ↓
必要时确认关键边界
  ↓
Agent 生成 Knowledge Bundle
  ↓
运行校验和可视化等项目工具
```

重要认知：

> 详细生成要求不应主要由用户手写，而应由 Agent 读取官方 SPEC 和源资料后自动分析制定。

用户主要提供：

- 源资料是什么；
- 目标用途是什么；
- 是否需要核心知识内化；
- 是否允许读取外链；
- 是否允许分析图片；
- 是否允许引入源资料外知识。

复杂的拆分策略、`type` 设计、index 组织、citation 设计，应由 Agent 自动完成，并在必要时向用户确认。

---

## 19. 工程实践素材：校验与可视化

以下工具脚本属于工程实践辅助能力，需要明确它们不是 OKF 协议本体。

### 19.1 共享解析模块

文件：

[tools/okf_bundle_common.py](assets/tools/okf_bundle_common.py)

用途：

- 解析 frontmatter；
- 扫描 bundle；
- 区分 concept document 和 reserved files；
- 计算 concept ID；
- 提取 Markdown links；
- 解析 bundle-relative absolute links 和 relative links；
- 提取 citations；
- 解析 log。

定位：

```text
项目级共享解析模块，不是 OKF 官方要求。
```

### 19.2 校验脚本

文件：

[tools/validate_okf_bundle.py](assets/tools/validate_okf_bundle.py)

定位：

```text
项目级 validator，不是 OKF required tooling。
```

它分三层：

| Profile | 含义 |
|---|---|
| `spec` | 检查官方 OKF v0.1 hard conformance |
| `reference` | 在 spec 基础上，对齐官方参考实现 |
| `project` | 在 reference 基础上，加入项目增强质量检查 |

这个分层可以避免把项目规则误说成官方协议要求。

### 19.3 可视化脚本

文件：

[tools/visualize_okf_bundle.py](assets/tools/visualize_okf_bundle.py)

定位：

```text
项目级 visualizer wrapper / extended viewer，不是 OKF required tooling。
```

它支持：

| Mode | 含义 |
|---|---|
| `official` | 调用官方 visualizer |
| `auto` | 优先官方，失败时 fallback |
| `extended` | 使用本地增强 viewer |

本地增强 viewer 使用官方同款库：

```html
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js"></script>
```

中文解释：

- Cytoscape.js 用于图谱渲染；
- marked 用于 Markdown 渲染。

注意：可视化工具用于辅助 review bundle，不是 OKF 协议本体。

---

## 20. 官方协议、官方参考实现、项目增强工具

今天最重要的工程认知之一是这个分层：

```text
OKF SPEC
  ↓
Official reference implementation
  ↓
Project tooling
```

### 20.1 OKF SPEC

官方格式规范，定义：

- 术语；
- bundle structure；
- concept document；
- conformance；
- index、log、citations、links 等规则。

这是判断什么叫 OKF 的根基。

### 20.2 官方参考实现

例如官方代码中的 `OKFDocument.validate()`。

它可能比 SPEC 更严格，例如要求：

```text
type
title
description
timestamp
```

但这属于官方参考实现行为，不等同于 SPEC hard conformance。

### 20.3 项目增强工具

例如：

- validator；
- visualizer；
- common parser；
- index coverage 检查；
- broken links 检查；
- citations 检查；
- HTML graph viewer。

这些工具有工程价值，但不是 OKF 协议本体。

一句话总结：

```text
SPEC 决定什么叫 OKF；
官方参考实现展示一种官方代码实践；
项目工具帮助生产、校验和浏览，但不构成协议要求。
```

---

## 21. 官方 visualizer 的实现观察

今天运行官方 visualizer 后，发现它对本地练习 bundle 的输出与预期不同：

```text
37 concept(s), 0 edge(s)
```

核验后原因是：

1. 官方 visualizer 当前只跳过 `index.md`，没有跳过 `log.md`，所以把 `log.md` 也算成 concept。
2. 官方 visualizer 当前忽略以 `/` 开头的 bundle-relative absolute links，所以没有生成 edges。

准确表达：

> 这是官方 visualizer 当前实现限制，不是 OKF SPEC 的问题。

因为官方 SPEC 明确推荐 bundle-relative absolute links。

---

## 22. 最终理解

今天最终可以这样理解 OKF：

> OKF v0.1 是一种开放的、对人类和 Agent 友好的知识表示格式，用于表示围绕数据和系统的元数据、上下文和整理后的洞察。它有意保持最小化，本质是一个带 YAML frontmatter 的 Markdown 文件目录树。OKF 的分发单位是 Knowledge Bundle；bundle 内的单个知识单元是 Concept，由一个 Markdown document 表示。`index.md` 和 `log.md` 是保留文件名，其他 `.md` 文件都是 concept documents。Concept ID 由文件路径去掉 `.md` 后缀得到。OKF conformance 要求非保留 `.md` 有可解析 frontmatter、frontmatter 有非空 `type`、reserved files 出现时结构正确。`title`、`description`、`resource`、`tags`、`timestamp` 是推荐字段，不是合规硬要求。Concepts 可以用标准 Markdown links 互相连接，推荐使用 bundle-relative absolute links；links 通常被视为有方向、无显式类型的关系。Citations 用来支持正文中来自外部材料的声明。OKF 不定义固定 type taxonomy，不规定存储、服务、查询基础设施，也不替代 OpenAPI、Protobuf 等领域 schema。它标准化互操作所需的少量规则，但不要求特定工具。

---

## 23. 最短记忆版

1. OKF 是开放的、对人类和 Agent 友好的知识表示格式。
2. OKF 的基本形态是 Markdown 文件目录树 + YAML frontmatter。
3. `Knowledge Bundle` 是分发单位，`Concept` 是 bundle 内的单个知识单元。
4. OKF v0.1 的硬性合规要求很少：非保留 `.md` 有 frontmatter、`type` 非空、reserved files 结构正确。
5. `title`、`description`、`resource`、`tags`、`timestamp` 是推荐字段，不是合规必需项。
6. Links 是标准 Markdown links，推荐 bundle-relative absolute links，通常表示有方向、无显式类型的关系。
7. Citations 用来支持正文中的外部来源声明。
8. OKF 不规定工具、存储、查询系统，也不定义固定 type taxonomy。
9. AI/Agent 可以生成 OKF bundle，但生成后应通过校验和人工 review。
10. Validator 和 visualizer 是工程辅助工具，不是 OKF 协议本体。

---

## 24. 复习自测

### 题目 1

OKF v0.1 的 hard conformance 包含哪些要求？

参考答案：

1. 每个非保留 `.md` 文件都有可解析 YAML frontmatter。
2. 每个 frontmatter 都包含非空 `type` 字段。
3. `index.md` 和 `log.md` 在出现时遵循官方结构。

### 题目 2

`type` 是官方固定枚举吗？

参考答案：

不是。`type` 字段是必需的，但 type 值没有中央注册表。Producer 应选择描述性、自解释的 type，consumer 必须优雅处理未知 type。

### 题目 3

为什么 OKF 推荐 bundle-relative absolute links？

参考答案：

因为它们以 `/` 开头，相对于 bundle root 解析。当文档在子目录中移动时，这种链接形式更稳定。

### 题目 4

Validator 和 visualizer 是 OKF 协议要求吗？

参考答案：

不是。它们是工程辅助工具。OKF 官方不要求特定 tooling。Validator 用于辅助检查，visualizer 用于辅助浏览和 review。

### 题目 5

Concept 与 Knowledge Bundle 的关系是什么？

参考答案：

Knowledge Bundle 是自包含、层级化的知识文档集合，是分发单位；Concept 是 bundle 内的单个知识单元，由一个 Markdown document 表示。
