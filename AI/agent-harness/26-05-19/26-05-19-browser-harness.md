# Browser Harness 共学笔记

> 日期：26-05-19  
> 主题：从安装、自然语言浏览器操作到前端调试与 helper 沉淀  
> 学习方式：以真实浏览器实操为主，逐步切换到“用户输入自然语言任务 → Agent 执行 → 复盘能力”的训练模式。

---

## 1. 学习总览

本次共学围绕 `browser-use/browser-harness` 展开，目标不是只学 API，而是理解它如何作为 AI Agent 的浏览器操作底座。

完整学习路径包括：

1. 理解 browser-harness 的定位。
2. 安装并连接隔离 Chrome。
3. 从底层 API 练习过渡到自然语言任务驱动。
4. 学习截图、坐标点击、输入、滚动、JS 提取。
5. 处理 X 搜索、登录墙、去噪、详情页、无限滚动和证据链追踪。
6. 体验 canvas 页游操作的特殊性和边界。
7. 理解 CloakBrowser、CDP、`BU_CDP_URL` 的连接关系。
8. 完成前端 bug 调试与综合练习。
9. 理解 `agent_helpers.py`、`domain-skills` 和 helper 沉淀机制。
10. 实际沉淀并验证 `get_debug_snapshot()` helper。
11. 学习干净卸载 browser-harness 的方法。

---

## 2. browser-harness 的定位

### 2.1 核心定义

browser-harness 是面向 LLM Agent 的真实浏览器控制工具。它通过 Chrome DevTools Protocol（CDP）连接真实 Chrome 或 Chromium 浏览器，让 Agent 能够像人一样操作浏览器。

它不是传统意义上的 Selenium/Playwright 测试脚本框架，而更像是：

```text
用户自然语言任务
    ↓
Claude Code / Codex / Agent
    ↓
browser-harness SKILL.md 指导 Agent 操作浏览器
    ↓
browser-harness CLI
    ↓
Chrome DevTools Protocol
    ↓
真实 Chrome 页面
```

### 2.2 与传统自动化工具的区别

| 工具 | 典型思路 |
|---|---|
| Selenium | 人写选择器和固定流程 |
| Playwright | 人写测试脚本或自动化脚本 |
| browser-use | 更完整的浏览器 Agent 框架 |
| browser-harness | 极薄 CDP 控制层，让 Agent 自己看、点、验证、沉淀 |

browser-harness 的重点是：

```text
截图观察 → 坐标点击 → 状态验证 → 必要时 JS/CDP 辅助
```

而不是一开始就写 selector。

---

## 3. 安装与连接隔离 Chrome

### 3.1 本次安装步骤

在学习目录中克隆仓库：

```bash
git clone https://github.com/browser-use/browser-harness.git
```

使用 `uv tool install -e` 安装：

```bash
uv tool install -e "/e/CodeLab/AiLab/browser-harness-learn/browser-harness"
```

安装后 CLI 位于：

```text
/c/Users/Administrator/.local/bin/browser-harness
```

### 3.2 诊断命令

```bash
browser-harness --doctor
```

最初诊断结果显示 Chrome 未运行，daemon 未连接。

### 3.3 隔离 Chrome 启动方式

选择“隔离 Chrome”而不是日常 Chrome，原因是：

- 不复用日常登录态。
- 使用单独 profile。
- 适合学习和自动化练习。

在 Windows 上使用 PowerShell 启动：

```bash
powershell.exe -NoProfile -Command "Start-Process -FilePath 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ArgumentList '--remote-debugging-port=9222','--user-data-dir=E:\CodeLab\AiLab\browser-harness-learn\chrome-profile','about:blank'"
```

验证 9222 端口：

```bash
powershell.exe -NoProfile -Command "Test-NetConnection 127.0.0.1 -Port 9222"
```

### 3.4 连接 browser-harness

使用 `BU_CDP_URL` 指定 CDP 地址：

```bash
BU_CDP_URL=http://127.0.0.1:9222 browser-harness <<'PY'
print(page_info())
PY
```

成功返回：

```python
{'url': 'about:blank', 'title': '', 'w': ..., 'h': ...}
```

---

## 4. 基础浏览器操作能力

### 4.1 打开页面与截图

示例：

```bash
BU_CDP_URL=http://127.0.0.1:9222 browser-harness <<'PY'
new_tab('https://github.com/browser-use/browser-harness')
wait_for_load()
print(page_info())
capture_screenshot()
PY
```

学习重点：

```text
打开页面后必须验证 page_info 和截图，不假设页面已经正确加载。
```

### 4.2 坐标点击

browser-harness 推荐截图优先、坐标点击优先。

流程：

```text
capture_screenshot()
→ 判断目标坐标
→ click_at_xy(x, y)
→ capture_screenshot()
→ 验证页面变化
```

学习中发现：

- 截图像素和 CSS 像素可能不同。
- 需要检查 `window.devicePixelRatio`。
- 本次环境中 `devicePixelRatio = 1`。

### 4.3 点击前校准

使用 `document.elementFromPoint(x, y)` 检查坐标命中元素：

```javascript
(() => {
  const e = document.elementFromPoint(165, 163);
  return {
    tag: e.tagName,
    text: e.innerText,
    href: e.closest('a')?.href
  };
})()
```

这个方法用于确认点击点是否真的命中目标。

### 4.4 输入框填写

练习页面中包含输入框和提交按钮。

流程：

```text
定位输入框 → 点击聚焦 → type_text() 输入 → 读回 value → 点击提交 → 验证结果
```

注意事项：

- `fill_input()` 在当前环境中出现字符重复。
- 因此输入后必须读回 `value` 验证。
- 更稳方式是 JS 清空再 `type_text()`。

---

## 5. 从 API 练习切换到自然语言任务

学习过程中明确：browser-harness 的最终使用方式不是用户手写 Python，而是用户用自然语言给 Agent 下任务。

实际分层：

```text
用户自然语言
    ↓
Agent 规划和判断
    ↓
browser-harness 底层动作
```

正确练习方式：

```text
我给出自然语言任务模板
用户输入任务
Agent 执行
Agent 复盘背后用到的 browser-harness 能力
```

---

## 6. X 搜索场景：登录墙、去噪、详情页、无限滚动

### 6.1 登录墙处理

任务：搜索 X 上“张雪机车”的最新帖子。

首次打开 X 搜索页时，被重定向到登录页：

```text
https://x.com/i/flow/login?redirect_after_login=...
```

处理原则：

```text
遇到登录墙，停止并让用户手动登录；不读取或输入密码、验证码。
```

### 6.2 搜索与提取

登录后访问：

```text
https://x.com/search?q=张雪机车&src=typed_query&f=live
```

`f=live` 表示“最新”。

通过 DOM 读取 `article` 节点，提取：

- 作者
- handle
- 发布时间
- 正文
- status 链接

### 6.3 结果去噪

去噪规则：

1. 关键词命中。
2. 语义相关。
3. 排除广告、刷量、代孕、垃圾信息、关键词误伤。
4. 区分高相关、低信息量、重复模板。

示例判断：

- “张雪机车再夺冠军”属于高相关，但可能重复。
- “代孕、捐卵、刷量”等属于垃圾噪声。
- “只提到关键词但主题是地域争论”属于边缘相关。

### 6.4 打开详情页

详情页适合提取：

- 完整正文
- 精确时间
- 互动数据
- 引用/回复上下文

搜索列表适合快速筛选，详情页适合精确提取。

### 6.5 无限滚动

X 会虚拟化列表，滚动后旧 DOM 可能消失。

正确策略：

```text
每一轮读取当前 DOM
→ 用 status 链接去重保存
→ 滚动
→ 等待
→ 再读取
```

错误策略：

```text
滚到底后一次性读取 DOM
```

因为旧帖子可能已经被虚拟列表移除。

### 6.6 证据链追踪

对“张雪机车年度冠军前景”做证据链追踪时，步骤是：

1. 搜索更精确关键词：`张雪机车 年度冠军`。
2. 找信息量最高或最像来源的帖子。
3. 打开详情页检查：
   - 正文
   - 时间
   - 图片
   - 视频
   - 引用帖
   - 外链
   - 来源标注
4. 区分：
   - 原始来源
   - 搬运
   - 二次转述
   - 用户观点
5. 输出可信度。

本次结论：

```text
X 上有多条传播和视频标注“来源：美丽浙江”，但缺少 WSBK 官方链接、美丽浙江原始链接或官方积分榜，因此可信度为中等，仍需外部官方来源核验。
```

---

## 7. 页游 canvas 操作经验

### 7.1 访问页游

访问：

```text
https://codomino.99.com/
```

登录后进入游戏大厅。

### 7.2 canvas 页面特点

DOM 中几乎没有文本，游戏内容绘制在 canvas 中。

特点：

```text
按钮不是 DOM 元素，而是画在 canvas 上。
```

因此只能依靠：

```text
截图识别 → 坐标点击 → 截图验证
```

### 7.3 坐标不稳定问题

多次出现想点 Domino，却误入 Mummy Reborn 的情况。

经验：

```text
canvas 游戏中坐标需要反复校准；误点风险高。
```

### 7.4 普通试玩一局

在用户明确说明这是测试游戏后，按普通玩家方式试玩 Mummy Reborn：

1. 进入玩法。
2. 观察下注金额 `10,000`。
3. 点击 `SPIN`。
4. 按钮变成 `STOP`，表示回合进行中。
5. 出现倍率 `x5`、`x13`，判断为特殊回合或免费旋转。
6. 等待按钮恢复 `SPIN`。
7. 最终赢分显示 `407,500`。

判断逻辑：

| 画面变化 | 判断 |
|---|---|
| `SPIN` → `STOP` | 回合进行中 |
| 出现倍率 | 触发特殊回合 |
| 符号持续变化 | 自动结算中 |
| `STOP` → `SPIN` | 回合结束 |
| 底部数字变化 | 本轮赢分 |

### 7.5 安全与边界

browser-harness 本身是浏览器控制层，安全判断由 Agent 层负责。

在页游场景中，默认避免：

- 充值
- 刷分
- 绕过反作弊
- 自动挂机
- 多人对局自动化
- 自动刷资源

用户明确授权测试后，可以进行普通玩家级试玩，但仍不做作弊或批量自动化。

---

## 8. CloakBrowser、CDP 与 BU_CDP_URL

### 8.1 browser-harness 连接模型

browser-harness 连接的是 CDP endpoint。

只要浏览器满足：

```text
基于 Chromium
开启 remote debugging
提供 /json/version 或 CDP WebSocket
browser-harness 能访问端口
```

理论上就能连接。

### 8.2 CloakBrowser 是否可连接

查询 `CloakHQ/CloakBrowser` 后确认：

- 它基于 Chromium。
- 支持 Playwright/Puppeteer。
- 支持 CDP remote connection。
- 支持 `--remote-debugging-port`。
- 支持 `connect_over_cdp("http://localhost:9222")`。

因此 browser-harness 可以通过 `BU_CDP_URL` 连接 CloakBrowser。

示例：

```bash
BU_CDP_URL=http://127.0.0.1:9242 browser-harness <<'PY'
print(page_info())
PY
```

### 8.3 BU_CDP_URL 配置方式

临时配置：

```bash
BU_CDP_URL=http://127.0.0.1:9222 browser-harness <<'PY'
print(page_info())
PY
```

当前 shell 配置：

```bash
export BU_CDP_URL=http://127.0.0.1:9222
```

多浏览器并行时配合 `BU_NAME`：

```bash
BU_NAME=cloak BU_CDP_URL=http://127.0.0.1:9242 browser-harness <<'PY'
print(page_info())
PY
```

---

## 9. 前端调试练习

### 9.1 简单 bug 页面

创建本地服务器：

```text
debug-practice-server.js
```

页面包含按钮：

```text
加载用户信息
```

点击后请求：

```text
GET /api/user
```

服务端故意返回：

```text
HTTP 500
```

响应体：

```json
{
  "error": "database unavailable",
  "requestId": "debug-practice-001"
}
```

### 9.2 调试流程

标准流程：

```text
打开页面
→ 截图初始状态
→ 安装 console/fetch 监听
→ 点击按钮
→ 截图异常状态
→ 读取 console/network/storage
→ 判断原因
```

### 9.3 结论

问题链路：

```text
点击按钮成功
→ fetch('/api/user') 成功发起
→ 服务端返回 500
→ 前端 throw Error
→ catch 后显示“加载失败”
```

根因：

```text
/api/user 后端接口异常，响应体提示 database unavailable。
```

---

## 10. 综合练习：本地用户资料调试页

### 10.1 综合练习页

创建本地服务器：

```text
comprehensive-practice-server.js
```

访问地址：

```text
http://127.0.0.1:8766
```

页面包含：

- 姓名
- 邮箱
- 手机号
- 用户类型
- 是否订阅
- 备注
- 保存草稿
- 提交资料
- 加载用户信息
- 清空表单
- 状态区域
- 结果区域

### 10.2 观察页面结构

第一步只观察，不操作。

识别字段：

```text
input#name
input#email
input#phone
select#userType
checkbox#subscribed
textarea#note
```

识别按钮：

```text
button#save-draft
button#submit-profile
button#load-user
button#clear-form
```

初始状态：

```text
尚未操作
```

### 10.3 填写表单并验证

填写内容：

```json
{
  "name": "Alice",
  "email": "alice@example.com",
  "phone": "13800138000",
  "userType": "test",
  "subscribed": true,
  "note": "browser-harness 综合练习"
}
```

验证方式：读取真实字段值，而不是只看截图。

### 10.4 保存草稿

点击“保存草稿”后，请求：

```text
POST /api/draft
```

返回：

```json
{
  "ok": true,
  "message": "草稿已保存"
}
```

同时写入：

```text
localStorage.lastDraft
```

判断：页面成功提示、network 200、localStorage 写入三者共同证明保存成功。

### 10.5 触发失败 API

点击“加载用户信息”后，请求：

```text
GET /api/user
```

返回：

```json
{
  "error": "database unavailable",
  "requestId": "comprehensive-debug-001"
}
```

状态码：

```text
500
```

最终判断：

```text
问题集中在 /api/user 后端接口，可能是数据库依赖异常。
```

---

## 11. agent_helpers.py 与沉淀机制

### 11.1 官方设计

browser-harness 提供 Agent 可编辑工作区：

```text
agent-workspace/agent_helpers.py
agent-workspace/domain-skills/
```

官方思想：

```text
The agent writes what's missing during execution.
```

也就是 Agent 在真实任务中发现缺失能力后，可以写入 helper 或 domain skill。

### 11.2 自动与非自动的边界

自动的是：

```text
helper 写入后，下次 browser-harness 自动加载。
domain-skills 启用后，goto_url 可按域名暴露相关 skill。
```

不是自动的是：

```text
browser-harness 不会后台自动总结和写文件。
```

更准确地说：

```text
写入不自动，复用自动。
```

### 11.3 agent_helpers.py 适合沉淀什么

适合：

- 前端调试监听
- 获取调试快照
- 表单读回验证
- 滚动收集和去重
- 等待状态文本

不适合：

- 登录 token
- 密码
- 一次性坐标
- 一次性测试数据
- 付款/删除/提交等高风险动作
- 游戏刷资源逻辑

### 11.4 domain-skills 适合沉淀什么

适合：

- 站点稳定 selector
- URL pattern
- 私有 API
- hidden wait
- framework quirk
- site-specific trap

不适合：

- 像素坐标
- 任务流水账
- 秘密信息

官方理念：

```text
Capture the durable shape of the site, not the diary.
```

---

## 12. 实际沉淀：get_debug_snapshot helper

### 12.1 用户要求

用户只要求沉淀：

```text
获取调试快照
```

因此只写入一个 helper：

```python
def get_debug_snapshot():
    from browser_harness.helpers import js

    return js(
        r"""
(() => ({
  visibleText: document.body ? document.body.innerText : '',
  console: window.__comprehensiveDebug?.console || window.__debugRun?.console || window.__debugPractice?.console || [],
  network: window.__comprehensiveDebug?.network || window.__debugRun?.network || window.__debugPractice?.network || [],
  localStorage: Object.fromEntries(Object.entries(localStorage)),
  sessionStorage: Object.fromEntries(Object.entries(sessionStorage)),
  url: location.href,
  title: document.title
}))()
"""
    )
```

位置：

```text
browser-harness/agent-workspace/agent_helpers.py
```

### 12.2 验证过程

第一次调用失败：

```text
NameError: name 'js' is not defined
```

原因：

```text
agent_helpers.py 作为独立模块加载，不能直接引用 helpers.py 中的 js 名称。
```

修复方式：

```python
from browser_harness.helpers import js
```

放在函数内部延迟导入。

再次验证成功：

```text
title: browser-harness 综合练习
url: http://127.0.0.1:8766/
network 数量: 2
localStorage: lastDraft
```

### 12.3 自然语言调用方式

用户可以说：

```text
请复现这个问题，然后用 get_debug_snapshot 收集页面可见文本、console、network、localStorage 和 sessionStorage，并基于快照判断问题原因。
```

Agent 实际调用：

```python
snapshot = get_debug_snapshot()
```

### 12.4 helper 的效果

沉淀后，自然语言任务变短，执行更稳定：

```text
不用每次重写 JS 读取 visibleText / console / network / storage。
```

---

## 13. 卸载与清理

### 13.1 停止 daemon

```bash
browser-harness --reload
```

### 13.2 卸载 uv tool

```bash
uv tool uninstall browser-harness
```

验证：

```bash
command -v browser-harness
uv tool list
```

### 13.3 删除仓库

```bash
rm -rf "/e/CodeLab/AiLab/browser-harness-learn/browser-harness"
```

注意：这会删除 `agent_helpers.py` 中沉淀的 helper。若要保留，应先备份。

### 13.4 删除隔离 Chrome profile

```bash
rm -rf "/e/CodeLab/AiLab/browser-harness-learn/chrome-profile"
```

该目录可能包含登录过的 cookie/session。

---

## 14. 常用自然语言任务模板

### 14.1 页面操作模板

```text
请打开 [网址]，先截图观察页面状态，然后完成 [目标]。每一步操作后截图验证。如果遇到登录、付费、验证码或不可逆操作，先停下来问我。
```

### 14.2 数据提取模板

```text
请打开 [网址]，提取 [数据类型]。先说明你会从哪些页面或区域提取，然后执行。结果要去重、标注来源链接，并说明哪些数据不确定。
```

### 14.3 前端调试模板

```text
请复现 [bug]。先截图初始状态，然后执行用户操作，读取 console、network、storage，最后判断是 UI、JS、接口、鉴权还是数据问题。
```

### 14.4 证据链模板

```text
请围绕 [说法] 做证据链追踪。先列出需要验证的事实，再找官方来源、媒体来源和用户转述，最后区分原始来源、二次传播和观点判断。
```

### 14.5 helper 调用模板

```text
请复现这个问题，然后用 get_debug_snapshot 收集页面可见文本、console、network、localStorage 和 sessionStorage，并基于快照判断问题原因。
```

---

## 15. 核心心法总结

browser-harness 的核心不是“自动点网页”，而是：

```text
观察 → 操作 → 验证 → 调试 → 复盘 → 沉淀
```

每一步都应有证据：

- 截图证明用户看到什么。
- DOM 值证明字段真实状态。
- Network 证明接口是否成功。
- Console 证明前端是否报错。
- Storage 证明本地状态是否变化。
- Helper 证明可复用经验被沉淀。

最终学习结论：

```text
browser-harness 是 AI Agent 操作真实 Chromium 浏览器的薄控制层。
它适合人工协作式网页操作、页面观察、复杂任务探索、前端调试和可复用经验沉淀。
它不适合无边界批量自动化、刷资源、绕过风控或高风险不可逆操作。
```
