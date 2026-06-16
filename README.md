# 🎣 偶渔学技

![BANNER](./BANNER.png)

## 📚 笔记索引

- [🧠 人工智能](#ai)
  - [🧬 模型训练](#model-training)
  - [🐎 驾驭智能](#agent-harness)
  - [🕵️ 知识检索](#agent-knowledge)

---

## <span id="ai">🧠 人工智能</span>

| 类目 | 笔记 | 日期 | MD | HTML |
|---|---|---|---|---|
| <span id="model-training">🧬 模型训练</span> | MiniMind / LLM 工程化训练 | 26-05-15 | [MD](./AI/model-training/26-05-15/26-05-15-minimind-llm-training-notes.md) | [HTML](https://babysource.github.io/fitful-tech-notes/AI/model-training/26-05-15/26-05-15-minimind-llm-training-notes.html) |
| <span id="agent-harness">🐎 驾驭智能</span> | Dynamic Workflows 学习笔记 | 26-06-09 | [MD](./AI/agent-harness/26-06-09/26-06-09-claude-code-dynamic-workflows.md) | [HTML](https://babysource.github.io/fitful-tech-notes/AI/agent-harness/26-06-09/26-06-09-claude-code-dynamic-workflows.html) |
|  | Browser Harness 共学笔记 | 26-05-19 | [MD](./AI/agent-harness/26-05-19/26-05-19-browser-harness.md) | [HTML](https://babysource.github.io/fitful-tech-notes/AI/agent-harness/26-05-19/26-05-19-browser-harness.html) |
| <span id="agent-knowledge">🕵️ 知识检索</span> | OKF（Open Knowledge Format）学习笔记 | 26-06-16 | [MD](./AI/agent-knowledge/26-06-16/26-06-16-okf-open-knowledge-format.md) | [HTML](https://babysource.github.io/fitful-tech-notes/AI/agent-knowledge/26-06-16/26-06-16-okf-open-knowledge-format.html) |

---

## 🤖 辅学技能（重塑学习范式）

![SKILLS](./SKILLS.png)

**辅学技能适用于智能体自主调用：**

- 🌱 **个性进化**：根据用户使用过程的个性偏好持续进化。
- 🔗 **软链安装**：推荐使用软链方式安装到全局技能目录。

### 🦉 辅学私教（聊即学）

---

**私教式辅学**：构建体系化知识的个性化研习方案并实施渐进式辅学指导。

#### 1）用法说明

- **适用场景**：需要围绕某个主题开展体系化学习、知识讲解、路径规划或渐进式答疑。
- **调用方式**：直接提出辅学目标或问题，也可使用 `/fitful-tech-tutor` 显式唤起。
- **场景示例**：

  > 请指导我完成 xxx 学习。

#### 2）安装说明

- **Windows**

```bat
:: 请在仓库根目录执行（示例：Claude Code 安装）

mklink /D "%USERPROFILE%\.claude\skills\fitful-tech-tutor" ".agents\skills\fitful-tech-tutor"
```

- **MacOS / Linux**

```bash
# 请在仓库根目录执行（示例：Claude Code 安装）

ln -s ".agents/skills/fitful-tech-tutor" "$HOME/.claude/skills/fitful-tech-tutor"
```

### ✍️ 辅学笔记（学即记）

---

**伴学式笔记**：将人机学习会话沉淀为结构化的 Markdown 笔记与可视化的 HTML 复习页面。

#### 1）用法说明

- **适用场景**：需要将完整学习会话整理为详尽、结构化、可复习的学习笔记与网页页面。
- **调用方式**：明确提出生成、整理或更新学习笔记，也可使用 `/fitful-tech-noter` 显式唤起。
- **场景示例**：

  > 将本次学的 xxx 整理成学习笔记。

#### 2）安装说明

- **Windows**

```bat
:: 请在仓库根目录执行（示例：Claude Code 安装）

mklink /D "%USERPROFILE%\.claude\skills\fitful-tech-noter" ".agents\skills\fitful-tech-noter"
```

- **MacOS / Linux**

```bash
# 请在仓库根目录执行（示例：Claude Code 安装）

ln -s ".agents/skills/fitful-tech-noter" "$HOME/.claude/skills/fitful-tech-noter"
```

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=babysource/fitful-tech-notes&type=Date&v=20260515)](https://www.star-history.com/#babysource/fitful-tech-notes&Date)
