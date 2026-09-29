# Docker Sandbox Kit 规范（v3）学习笔记

> 沉淀日期：2026-09-29
> 主要来源：[docker/sandbox-kit-spec](https://github.com/docker/sandbox-kit-spec)（README、`docs/kit-intro.md`、`docs/spec/SPEC-v3.md` §7.4、`docs/spec/capabilities/`）、[Docker Sandboxes 安装文档](https://docs.docker.com/ai/sandboxes/install/)、[Docker 官方博客](https://www.docker.com/blog/docker-sandbox-kit-spec/)
> 标记约定：【事实】规范/文档原文可查证；【推理】从事实推导的结论；【类比】辅助理解的模型（附边界）；【待核验】本次未验证、需后续确认

---

## 1. 痛点：Dockerfile 之后的另一半

【事实】Dockerfile 完整回答了镜像**内部**的一切：怎么构建、打包什么、怎么启动（entrypoint、cmd、env、user、workdir）。但它对镜像**外部**只字未提。

【事实】Agent 不是静态应用负载，而是**行动者**（actor）：它主动决定下一步做什么，然后对文件系统、网络、数据库、云账号施加操作。这种授权不是缺陷，而是 agent 能干活的前提——不能装依赖、不能调 API、不能持凭据的 agent 无法完成工作。

【事实】在 Kit 出现之前，"agent 需要哪些权限和资源"分布在：`docker run` 参数、Compose 文件、CI 配置、入职文档、以及配置者的记忆中——**在制品之外、不受版本管理、无法审查**。

【推理】核心问题不是"agent 会越权"，而是**授权本身不可见、不可版本化**。能被审查的前提是信息存在制品内；存在制品内才能版本化；可版本化才能 diff；可 diff 才能拦截审批。这条推导链是整个规范的价值基础。

> **Dockerfiles made software reproducible. Kits make authority reproducible.**
> （Dockerfile 让软件可复现，Kit 让授权可复现。）

【事实】规范定位：开放规范（Apache 2.0）而非产品特性。官方宣传语为 "Authority as Code"。当前为**实验性**状态，目标 **2026 Q4** 定稿。

---

## 2. Kit 的物理制品模型 ★核心承重墙

> **一个 Kit 在物理上就是一个普通 OCI 镜像：**
> - **层（layers）** 装**内容**（工具、文件系统）
> - **manifest 注解** `vnd.docker.sandbox.kit.descriptor` 装**声明**（descriptor，即申请单）
> - **一个 digest 把两者钉死在一起**

【事实】没有 Kit 专用 media type、没有 artifactType、没有旁车文件（sidecar）。因此：

- `docker pull` 照常拉取，`regctl` 照常检查，任何注册表照常存储
- 可以被任何镜像 `FROM`
- 不认识注解的引擎把它当普通镜像运行
- 扫描器、签名器、镜像同步工具零改动

【推理】"声明与内容同一制品、同一 digest"意味着 Kit 不可能被"半更新"：锁 digest 就同时锁定了内容、策略、元数据。分离的描述文件必然漂移（第二事实源问题）。

### 两类 Kit

| 类型 | 层的内容 | 每次组合的数量 |
|---|---|---|
| **workload** | 根文件系统；镜像 config 提供入口点/环境 | 恰好一个 |
| **mixin** | 叠加在 workload 文件系统上的 overlay；可以无内容纯声明 | 零或多个 |

【事实】descriptor 刻意**不重复**镜像已能表达的信息：无顶层身份名、无镜像引用、无 entrypoint/env——那些是镜像 config 的职责。重复即产生"一个问题两个答案"，其中之一必然过期。

---

## 3. 两个角色：沙箱运行时与 Kit

【事实】沙箱（Docker Sandboxes / `sbx`）= **microVM**，自带独立内核和私有 Docker 引擎，提供"强制而非商量"的隔离边界。

【类比】沙箱 = 毛坯房 + 门禁系统（运行时提供）；Kit = 家具 + 一份"我需要开哪些门"的申请表（内容 + 权限声明）。
【类比边界】此类比止于"隔离与内容的分工"；不涵盖权限的版本化审查机制。

【事实】宿主机平台与沙箱内部环境是两个独立概念：
- **宿主机**（装 sbx 的机器）：macOS Sonoma+（Apple silicon）、Windows 11、Ubuntu 24.04+；本地沙箱还需 Hypervisor Platform / KVM
- **沙箱内部**：Linux 用户态（见 §8）

---

## 4. 编写与构建

### 四种编写形式【事实】

| 形式 | 构成 | 特点 |
|---|---|---|
| 伴生对（默认） | `<主干>.yaml` + 同主干 `.dockerfile` | Dockerfile 工具链照常工作 |
| 内联 `build:` 块 | descriptor 内嵌 Dockerfile 文本 | 单文件 |
| 注释 descriptor | Dockerfile 的 `# kit:` 注释块携带声明 | 一文件两用 |
| **Kit set** | `kits:` 列表引用其他 Kit | **唯一配方不是 Dockerfile 的形式** |

### 构建命令【事实】

```console
$ docker buildx build . -f gh.yaml -t docker.io/me/sbx-kit-gh:2.72.0
$ docker buildx build . -f gh.yaml --build-arg version=2.99.0 -t gh-kit:2.99.0   # 带 args
```

命令解剖：

- `.` = **构建上下文**：整个目录打包发给构建器（伴生文件、`contentFile` 引用的文件都必须在其中）
- `-f gh.yaml` = 入口文件（平时放 Dockerfile 的位置）
- 首行 `# syntax=docker/sandbox-kit:3` 触发 BuildKit **自动拉取 Kit 前端**（`docker/sandbox-kit:3` 镜像）
- `docker build` 与 `docker buildx build` 在现代 Docker 中是同一条命令

### 前端流水线【事实】

1. **严格校验** descriptor：任何无法识别的字段直接报错（`KnownFields(true)`）——拼错的键等于静默缺失的策略，必须失败
2. 按文件名主干在上下文中找到伴生 Dockerfile（或在 descriptor 中用 `dockerfile:` 字段显式指定）
3. 把 Dockerfile 原样交给常规 Dockerfile 构建器（`dockerfile.v0`）
4. 将 guidance 内容（如 agent-context 的 `contentFile`）staged 进镜像
5. 将 descriptor 作为 manifest 注解附加——产出**一个普通镜像**

【推理】Kit 前端是"总装工头"：调用老工人（Dockerfile 构建器）干活，最后往包装箱上多贴一张单子（注解）。

### 镜像构建基础（补课要点）

【事实】OCI 镜像 = ① 一叠只读层（每层是文件系统变化的 tar 包）+ ② config（JSON：入口点/环境/用户）+ ③ manifest（拼装说明，可挂注解）。

【事实】`docker build` 逐条执行 Dockerfile 指令；每条 `RUN` 在临时容器中**真实执行**，文件系统变化拍成一层；`ENTRYPOINT`/`ENV` 写入 config 而非层。多阶段构建中只有最后阶段的层进入最终镜像（`FROM scratch` + `COPY --from` 用于丢弃构建工具、只留成品）。

【类比】Git：层 ≈ commit 的 diff，digest ≈ commit hash，manifest ≈ 仓库元信息。
【类比边界】镜像层是只读叠加，没有分支/合并语义。

【事实】mixin 用 `FROM scratch` 构建纯 overlay（如 gh 示例用 nix 闭包自带全部依赖），可落在任何 workload 上；mixin 也可设 ENTRYPOINT（它仍是可独立运行的镜像），但组合时被忽略——workload 锚定运行时契约。

---

## 5. capabilities：统一申请模型

【事实】Kit 对宿主的一切请求都是 `capabilities` 列表中**带类型、带版本**的条目。资源授予（卷、端口、设备）与引擎执行的行为（生命周期钩子、agent 上下文）走同一清单——宿主机通过一种机制回答全部请求，或诚实地拒绝无法满足的部分。

```yaml
capabilities:
  - type: com.docker.sandbox/network-policy@1     # 网络申请
    config:
      runtime:
        allow: [github.com, api.github.com, uploads.github.com]
  - type: com.docker.sandbox/credential@1         # 凭据申请
    optional: true                                 # 给不了则跳过并记录
    config:
      service: github
      apiKey: {name: GH_TOKEN, proxyManaged: true}
  - type: com.docker.sandbox/agent-context@1      # 给 agent 的使用说明
    config:
      contentFile: ./gh-context.md
```

【事实】`@1` 是该类型 **config schema 的版本号**：类型可独立演进（`@2` 与 `@1` 并存），不需要 descriptor 语法升级。知名类型每型一页规范（`docs/spec/capabilities/com.docker.sandbox/`），未知类型以不透明方式携带（宿主可支持私有类型）。

【事实】`required` 无法满足 → 解析失败（fail closed）；`optional` 无法满足 → 跳过并记录。

### 平台底座（platform floor）【事实·规范原文】

> Kit 内容可以假定符合规范的运行时提供以下底座：`bash` 和 `sh`、`curl`、`git`、已填充的 CA store、以及名为 `agent`（uid `1000`，home `/home/agent`）的非 root 默认用户。其余一切 Kit 需要的东西，由它自己安装或携带。

【事实】Docker 维护了加固模板镜像 `dhi.io/sbx-templates:*` 预置底座。**关键坑**：拿裸发行版镜像构建——**构建成功、agent 启动失败**（"能构建 ≠ 能运行"）。自建路线必须自行补齐底座：

```dockerfile
FROM alpine:3.20
RUN apk add --no-cache bash curl git ca-certificates \
 && adduser -D -u 1000 agent
```

【推理】`sbx-templates` 是**便利品而非约束来源**：不用它获得的是**发行版选择自由**（debian/alpine/自制 rootfs），不是**操作系统自由**（见 §8）。

---

## 6. 组合与发布

### 组合语义【事实】

启动一个集合：一个 workload + 任意多个 mixin。符合规范的运行时将集合视为**封闭的**：

- 每个 `requires` 必须在集合内满足，否则解析失败；不隐式抓取任何东西
- `conflicts` 冲突直接失败
- 恰好一个 workload
- **按依赖图排序**而非参数输入顺序 → 同一集合永远组合出同一镜像（纯函数）→ 可锁定、可复现、可缓存

| 合并项 | 规则 |
|---|---|
| 文件层 | 各 mixin 依次叠加在 workload 上 |
| 网络规则 | 取**并集** |
| 生命周期钩子 | 按依赖顺序拼接 |
| guidance | 合成一份文档 |
| 不兼容请求 | 构建失败（不选赢家） |

### kind: set——整套发布【事实】

```yaml
# team-myagent.yaml
# syntax=docker/sandbox-kit:3
schemaVersion: "3"
kind: set
displayName: 我的 Agent 全套环境
version: "1.0.0"
kits:
  - ref: docker.io/dockerdev/sbx-kit-shell:1.0.0          # workload
  - ref: docker.io/dockerdev/sbx-kit-claude-mixin:2.1.6   # agent 本体
  - ref: docker.io/me/sbx-kit-gh:2.72.0
  - ref: docker.io/me/sbx-kit-node:22.0.0
```

- `kits:` 列表**就是** set 的配方——它没有也不需要 Dockerfile
- 成员必须是注册表引用（本地路径/git URL 被拒绝）；发布时每项按 digest 钉死
- 构建时解析每个成员、校验集合一致性、**合并成一个普通 Kit** 发布
- 消费端一条引用跑全套：`sbx run docker.io/me/team-myagent:1.0.0 .`

【事实】代价：合并产物是**钉死的制品**（pinned artifact）——升级任何一个成员都要重新发布整个 set。两种消费方式各有位置：固定 set（团队标准环境/CI，稳定可复现）vs 运行时现场组合（本地开发，灵活）。

### 文件账本【推理·汇总】

| 处境 | 需亲手写的文件 |
|---|---|
| 需要的 Kit 全有人发布 | **0 个**（直接 `sbx run` 引用）；固化分享才 +1 个 `set.yaml` |
| 现成 + 1 个自研工具 | 工具 1 对（yaml+dockerfile）+ 可选 set = 2~3 个 |
| 全套自建 | workload 1 对 + 每工具 1 对 + set 1 个 = (N+1)×2+1 |
| 最小单文件 Kit | 1 个（内联 `build:` 或 `# kit:` 注释块） |

【推理】每个"对"是一次性成本：写一次、发布、全团队复用。类比 `package.json`——依赖列表里一百个包不等于要写一百个包的代码。

### 多架构【事实】

Kit 是普通 OCI 镜像，multi-arch 原生支持（gh 示例的 nix 构建同时产出 `x86_64-linux` 与 `aarch64-linux`）。

---

## 7. 审查与强制：两道门 ★易混点

> **"agent 新版多要一个域名"不是普通软件升级，而是授权变更——它必然显式可见，可被拦截审批。**

### 为什么"只改一行版本号"就足以触发审查【推理链】

```
版本号/tag/digest → 唯一确定不可变镜像 → manifest 注解里有完整声明 → 新旧权限面可机械对比
```

老世界里同样"只改版本号"却无法审查：权限活在制品外，版本号变化不携带权限信息，**没有可 diff 的对象**。能不能审查，取决于信息存在哪。

【类比】手机 App 更新提示"此应用新增权限：通讯录"——因为权限清单写在 App 清单文件里、随版本走，系统对比新旧清单。Kit 把这套机制搬给 agent 沙箱。
【类比边界】手机类比止于"声明随版本走 + 系统对比"；不对应 Kit 的运行时网络强制执行。

### 门一：升级闸门（SPEC §7.4）【事实·规范原文】

descriptor 投影为**权限面**（permission surface）：宿主机必须授予的一切的归一化集合（分阶段的网络 allow/deny 列表、各阶段凭据、存储路径、skills 路径、端口、USB 匹配、privileged，以及其他类型的 `type+config-digest` 条目）。

**会拦截更新的消费方把 Kit 的权限面存入 lock，并将候选版本的权限面与之对比：**

- 版本变动但权限面**未扩大** → **MAY** 静默应用
- 任何**扩大** → **MUST** 停下等待批准：
  - 新增 allow 条目
  - **删除 deny 条目**（deny 本身是授权可接受的一部分）
  - 新凭据、新路径、新端口、新 USB 匹配、privileged
  - 对已授予只读的 skills 路径申请写权限
  - 其他类型请求的任何 config 变更
- `optional` 不改变权限面（它只改变"给不了怎么办"，不改变"给得了给什么"）
- `resources`、`lifecycle`、`agent-context`、`agent-sessions`、`sbx`、`long-running` 不计入权限面（约束自身或沙箱内行为，不获取访问权）
- args 展开后的值计入投影——**用参数扩大策略同样过闸门**

### 门二：运行门禁【事实】

沙箱内 agent 访问 allow 列表外的域名 → network-policy 由运行时**强制执行**，直接拦截。声明不是 agent 的自律，是门禁的名单。

### 两道门对照（防混淆）★

| | 升级闸门（§7.4） | 运行门禁 |
|---|---|---|
| 时机 | 改版本号后启动时 | agent 运行全程 |
| 谁比 | 运行时：新权限面 vs **lock 中的旧权限面** | 运行时：实际动作 vs **allowlist** |
| 结果 | 扩权 MUST 停批；未扩 MAY 静默 | 清单外直接拦截 |

### 其他可见位置【事实】

- **制品对比**：两版本都是普通镜像，`regctl` / `docker buildx imagetools inspect` 可拉出 manifest 注解做文本 diff
- **Code Review**：按 digest 锁版本时，PR 改一行 digest + 注解 diff 即权限变更审查
- **lock 文件 diff**：lock 记录权限面，其 diff 天然展示权限变化

---

## 8. 平台边界与约束归属 ★易混点

### 三层拆解："仅支持 Linux 生态吗"【推理·分层】

| 层 | 结论 | 依据 |
|---|---|---|
| ① 制品格式 | 理论上 OS 中立 | Kit 就是 OCI 镜像 + 注解，未发明新格式；OCI 存在 Windows 镜像先例 |
| ② 规范契约 | **钉在 Linux 用户态** | 平台底座（bash/curl/git/CA/`agent` 用户）全部是 Linux 惯用语；任何符合规范的运行时都必须提供这套底座 |
| ③ 实现生态 | 今天 100% Linux | sbx = Linux microVM；已发布 Kit、examples、`sbx-templates` 清一色 Linux 用户态 |

### 两道锁的归属★

| 约束 | 主人 | 层级 |
|---|---|---|
| 底座契约（bash/curl/git/CA/agent 用户）→ Linux 用户态 | **Kit 规范** | 制品契约层 |
| 用 Linux 内核的 microVM 实现 | **sbx 运行时** | 实现选择层 |

【事实】规范全文没有"microVM"要求。十大原则之一：

> **The grammar declares; runtimes behave.** descriptor 说*要什么*，从不说宿主*怎么给*。实现不了的能力应诚实地拒绝，而不是近似。

【推理】一致性测试考核**行为**而非**机制**——第二个运行时可以完全换掉隔离技术（gVisor、Firecracker、其他），但只要符合规范，服务的仍是 Linux 用户态的 Kit（底座契约推导所致）。逃出 Linux 的唯一途径是规范本身演进，不是换运行时。

【类比】浏览器：workload Kit ≈ 网页，规范底座 ≈ HTML 标准，sbx ≈ Chrome，microVM ≈ Blink 渲染引擎。写网页满足的是 HTML 标准而非 Chrome 私有行为；换浏览器照样跑，但网页内容仍是 HTML。
【类比边界】W3C 与 Docker 单一主导方的治理结构不同；"标准中立"目前是架构意图而非多方验证的事实（见下）。

【事实·现实注脚】今天 sbx 几乎是唯一成熟的符合规范的运行时——"满足规范契约"与"能在 sbx 上跑"暂时重合。约束归属是规范级的，但验证手段目前只有 sbx。

### 异构系统怎么办

| 需求 | 结论 |
|---|---|
| **Windows 用户态** workload | ❌ 规范不支持；需走 Kit 之外的产品路线（Windows VM/容器） |
| agent **运行在 Android 里**（形态 A） | ❌ Android 用户态（bionic/ART）不是标准 Linux 发行版，底座契约对不上 |
| agent 在 Linux 沙箱里**操控** Android（形态 B） | ✅ 可行：`com.docker.sandbox/usb-device@1` 接 USB 真机 + adb 工具链 mixin；或沙箱内跑 Android 模拟器容器【待核验：社区方案（如 dockerify-android）的性能与嵌套虚拟化】 |

【推理】"跑什么"≠"能操作什么"：边界画在沙箱墙内侧。Linux 沙箱可作为基地操控异构系统（adb / SSH / 云 API）。

---

## 9. 评估与采用（2026-09 时点）

### 成熟度【事实】

- 状态：实验性（Experimental），Apache 2.0，目标 **2026 Q4** 定稿
- 演进承诺：增量式——能力类型独立版本化（`@1`/`@2` 并存发布），descriptor 级 `schemaVersion` 升级是最后手段
- 版本断层：Docker Hub 上 `docker` org 发 v3，`sbx` org 是旧 v2 线，官方明言**不要混用**

### 采用信号

| 值得上 | 缓一缓 |
|---|---|
| agent 已跑在沙箱且在 Docker 生态（零迁移成本） | 工作站不在 sbx 支持平台（如 Windows 10） |
| 有审计/合规压力（权限变更可 diff 可审批） | 需要规范级稳定（等 Q4 定稿） |
| 多人/多机/多环境复用需求（set 一条引用） | 团队连 Dockerfile 都未铺开（先解决内容复现） |
| 担心供应商锁定（开放规范 + 一致性测试） | |

### 风险清单

1. **语法会动**：承诺 additive，但 `@2` 出现后有兼容矩阵要管
2. **单一参考实现**：规范开放，主力运行时只有 sbx；"不是锁定"待第二个实现验证
3. **组合即信任传递**：组合权限面 = 各成员申请的**并集**；用别人的 Kit = 信任其申请清单；闸门把关，审批责任在使用方
4. **v2/v3 并存期**：文档、包、教程两代混杂

### 行动路径（Windows 10 环境）

- **现在可做**：构建路径——`docker buildx build -f gh.yaml` + `docker buildx imagetools inspect` 看注解（只需 Docker Desktop，产物为普通镜像，不算押注）
- **持续观察**：Q4 2026 定稿动向；第二个运行时实现是否出现
- **上真沙箱**：等 Windows 11 环境，或云模式（`sbx --cloud`，同 Kit 引用，不挂载本地工作区）

---

## 10. 易错点辨析（验收沉淀）

1. **"物理是什么" vs "怎么写"**：Kit 物理上 = 普通 OCI 镜像（层装内容 + manifest 注解装声明 + 一个 digest）；"一工具一 Kit / 伴生文件"是编写粒度与形式。被问"是什么"不要答"怎么写"。
2. **两道门不可混**：升级闸门比 **lock 里的权限面**（§7.4，扩权 MUST 停批）；运行门禁查 **allowlist**（清单外拦截）。前者管"版本变化带来的授权变化"，后者管"运行时的实际动作"。
3. **组合权限 = 并集**：多工具组合后权限面是全体成员申请的并集，闸门照常把守——这是"组合即信任传递"的基础。
4. **"越权" ≠ 问题本质**：问题不是 agent 会越权，而是授权不可见、不可版本化；agent 拿权限是特性，散落在外才是缺陷。
5. **set 没有 Dockerfile**：`kits:` 列表就是配方——四种编写形式中唯一非 Dockerfile 的。
6. **`sbx-templates` 不是平台锁**：不用它可换发行版（自己补底座），换不了操作系统（底座契约 + 运行时内核两道锁）。
7. **"仅 Linux"要说准**：沙箱内运行环境钉在 Linux 用户态（规范级）；宿主机平台无关（sbx 支持 macOS/Win11/Ubuntu）；格式理论 OS 中立。

---

## 11. 命令速查

```console
# 构建 Kit（Win10 可行，只需 Docker Desktop + buildx）
docker buildx build . -f gh.yaml -t docker.io/me/sbx-kit-gh:2.72.0
docker buildx build . -f gh.yaml --build-arg version=2.99.0 -t gh-kit:2.99.0

# 查看镜像 manifest（验证声明在注解里）
docker buildx imagetools inspect docker.io/me/sbx-kit-gh:2.72.0

# 安装 sbx（Win11/macOS Sonoma+/Ubuntu 24.04+）
winget install -h Docker.sbx        # Windows
brew install docker/tap/sbx         # macOS
sbx login                            # Docker OAuth

# 运行（本地/云同 Kit 引用；云不挂载宿主工作区）
sbx run docker.io/dockerdev/sbx-kit-shell:1.0.0 docker.io/me/sbx-kit-gh:2.72.0 .
sbx --cloud …
```

浏览已发布 Kit：Docker Hub `type=sbx_kit` + Verified Publisher（`docker` org = v3，`sbx` org = v2，勿混用）。

---

## 12. 类比总录（含边界）

| 类比 | 对应 | 边界 |
|---|---|---|
| 手机 App 权限提示 | 声明随版本走 + 系统对比新旧清单（升级闸门） | 不对应运行时网络强制；App 权限粒度与 capabilities 类型不同构 |
| 浏览器（网页/HTML/Chrome/Blink） | workload/规范/sbx/microVM 的归属分层 | 治理结构不同：HTML 有多方标准组织，Kit 规范目前 Docker 单一主导 |
| Git（commit/diff/hash） | 层/文件系统变化/digest | 镜像层只读叠加，无分支合并语义 |
| 毛坯房 + 家具 + 申请表 | 沙箱隔离 / Kit 内容 / Kit 声明的分工 | 止于分工；不涵盖版本化审查 |
| package.json | 已发布 Kit 引用免费、文件账本趋近于零 | npm 依赖无"权限面"概念 |
| 总装工头 / 装订机 | Kit 前端：调用 Dockerfile 构建 + 贴注解 | 止于编排角色，不含校验细节 |

---

## 待核验清单

- [ ] `dhi.io/sbx-templates:*` 的实际标签列表与基础发行版（规范未展开）
- [ ] Android 模拟器容器方案（dockerify-android 等）在沙箱 microVM 内的性能与嵌套虚拟化可行性
- [ ] 2026 Q4 定稿的实际落地情况与语法变化
- [ ] sbx 在 Windows 10 上 winget 安装的实际行为（官方仅支持 Win11）
- [ ] `sbx run` 的确切命令行语法细节（本次纸面实践采用 README/kit-intro 可证形式）

---

## 掌握状态（阶段反馈）

- 已焊牢：痛点推导链、组合模型（workload/mixin/set）、约束归属（规范 vs 运行时）、平台边界
- 验收暴露的薄弱点（已转化为 §10 易错点 1/2/3）：物理制品模型的一句话表述、两道门的区分、组合权限并集
- 后续实践里程碑：Win10 构建路径实操（build + inspect，治"物理模型"薄弱点最直接）→ Win11 后 sbx 实操（亲历升级闸门）
