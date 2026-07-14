# RepoPilot

参考 Claude Code 架构设计的 AI 编程助手。基于 Anthropic SDK 原生构建，涵盖 Skill 分层路由、自进化记忆沉淀、分层上下文压缩、中心化多 Agent 协作、权限与安全审查五大核心能力。

## 架构设计

系统自上而下分为三层：

**交互层** — CLI / REPL（Typer + Rich）负责用户交互。

**安全层** — 权限检查器在工具执行前，强制执行 deny-first 规则和安全审查。

**执行层** — Agent Loop（查询循环 + 工具调度）协调五大核心模块：

- **工具集** — read、write、edit、glob、grep、bash
- **Skill 路由** — 加载器、路由器、Skill 工具（二阶段路由 + 渐进式加载）
- **记忆系统** — 存储、索引、进化引擎（自进化知识库）
- **上下文管理** — Token 计数、缓存、压缩器（三层压缩管线）
- **子 Agent** — 生成、并行执行、受限工具集

## 核心技术亮点

### 1. Skill 分层路由

二阶段路由 + 渐进式上下文加载：
- **第一阶段 — 粗召回**：基于关键词 + 标签匹配，快速筛选候选 Skill
- **第二阶段 — 精排**：LLM 仅根据 frontmatter 元信息对候选进行评分排序（不加载全文）
- **渐进式加载**：启动时只扫描 YAML frontmatter，调用时才加载 Skill 全文
- 解决问题：检索噪声、功能重叠、Token 成本增长

### 2. 自进化记忆沉淀

闭环记忆系统：执行 → 反思 → 提炼 → 分类存储 → 索引更新 → 按需复用
- **5 种记忆类型**：user（用户画像）、feedback（行为反馈）、project（项目状态）、reference（外部引用）、procedural（程序性经验）
- **文件化存储**：Markdown 文件 + YAML frontmatter + MEMORY.md 索引
- **TF-IDF 检索**：关键词匹配 + IDF 权重 + 时间衰减
- **自动反思**：LLM 分析会话历史，提取可复用知识

### 3. 分层上下文压缩

三层压缩管线，成本从低到高依次触发：
- **第一层 — 微压缩**：截断过大的工具输出，仅保留最近 N 个完整结果
- **第二层 — 上下文折叠（70%）**：将旧的 tool_call/tool_result 对折叠为单行摘要
- **第三层 — 自动压缩（85%）**：LLM 生成结构化摘要，保留 system prompt 和工具定义不变

### 4. 中心化多 Agent 协作

中心编排模式，主 Agent 控制子 Agent 执行：
- 子 Agent 以 tool_call 方式生成（不移交控制权）
- 独立上下文窗口 + 受限工具集
- 通过 ThreadPoolExecutor 支持并行执行
- 路径边界限制，确保安全隔离

### 5. 权限与安全审查

多层安全链：
- **规则引擎**：deny-first 语义（deny 始终优先于 allow）
- **工具分级**：read_only / write / dangerous 三级分类
- **Bash 安全**：危险命令模式匹配（rm -rf、sudo、curl|bash 等）
- **Prompt 注入检测**：正则匹配指令覆盖、角色劫持、系统标签注入
- **路径穿越检测**：阻止访问敏感系统路径
- **沙箱**：工作目录限制 + 敏感环境变量过滤

## 技术栈

- **LLM 接口** — `anthropic` SDK（tool use、streaming、prompt caching）
- **数据模型** — `pydantic`
- **命令行** — `typer`
- **终端界面** — `rich`（Markdown 渲染、Panel、Spinner）
- **交互式 REPL** — `prompt-toolkit`（历史记录、自动补全）
- **记忆存储** — Markdown 文件 + YAML frontmatter
- **配置管理** — JSON（分层加载：全局 → 项目 → 本地）

## 快速开始

### 1. 环境要求

- Python >= 3.10
- Anthropic API Key（支持 Claude 模型的 API 密钥）

### 2. 克隆并安装

```bash
git clone https://github.com/msmzy/agent.git
cd agent

# 安装项目（开发模式）
pip install -e .

# 如需运行测试，安装开发依赖
pip install -e ".[dev]"
```

### 3. 配置 API Key

```bash
# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-api03-你的密钥"

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-api03-你的密钥"

# Windows (CMD)
set ANTHROPIC_API_KEY=sk-ant-api03-你的密钥

# 永久生效（写入 shell 配置文件）
echo 'export ANTHROPIC_API_KEY="sk-ant-api03-你的密钥"' >> ~/.bashrc
source ~/.bashrc
```

### 4. 初始化项目

```bash
# 在你的代码项目目录下执行
cd /path/to/your/project
repopilot init
```

这会创建 `.repopilot/` 目录，包含配置文件、记忆存储和 Skill 目录。

### 5. 使用方式

有两种使用方式：

#### 方式一：交互式 REPL（推荐）

```bash
repopilot chat
```

进入交互式对话模式，你可以：
- 直接输入问题或任务，Agent 会调用工具自动完成
- 输入 `/help` 查看所有命令
- 输入 `/exit` 退出

示例对话：
```
> 分析当前项目的目录结构
> 读取 main.py 并解释它的逻辑
> 找到所有包含 TODO 的文件
> /skills    # 查看可用的 Skill
> /usage     # 查看 Token 消耗
> /exit      # 退出
```

#### 方式二：单次任务执行

```bash
repopilot run "帮我分析 src/ 目录下的代码结构"
repopilot run "读取 pyproject.toml，列出所有依赖"
repopilot run "找到所有 Python 文件中的 TODO 注释"
```

#### 命令行选项

```bash
# 指定模型
repopilot chat --model claude-sonnet-4-6

# 指定工作目录
repopilot chat --dir /path/to/project

# 设置权限模式（default=需确认, auto-edit=自动批准文件编辑, plan=只读）
repopilot chat --permission-mode auto-edit
```

### 6. 运行测试

```bash
pytest tests/ -v
```

### REPL 命令

- `/help` — 查看可用命令
- `/clear` — 清空对话历史
- `/usage` — 查看 Token 消耗统计
- `/mode` — 切换权限模式
- `/memory` — 查看已加载的记忆
- `/skills` — 列出可用的 Skill
- `/exit` — 退出 RepoPilot

## 配置说明

配置按层级加载（后者覆盖前者）：

1. `~/.repopilot/settings.json`（全局配置）
2. `.repopilot/settings.json`（项目配置）
3. `.repopilot/settings.local.json`（本地配置，已 gitignore）

```json
{
  "model": "claude-sonnet-4-6",
  "max_tokens": 8192,
  "max_iterations": 50,
  "permission_mode": "default",
  "permissions": [
    {"tool": "bash", "pattern": "npm *", "action": "allow"}
  ],
  "deny_rules": [
    {"tool": "bash", "pattern": "*rm -rf*", "action": "deny"}
  ]
}
```

## 自定义 Skill

在 `.repopilot/skills/<skill-name>/` 目录下创建 `SKILL.md` 文件：

```markdown
---
name: my-skill
description: 这个 Skill 的功能描述
triggers:
  - /my-skill
  - 触发关键词
tags:
  - 分类标签
applicable_when: 适用场景
not_applicable_when: 不适用场景
---

# 当此 Skill 被调用时，Agent 执行的指令
...
```

## 测试

```bash
pip install -e ".[dev]"
pytest tests/
```

## 项目结构

```
repopilot/
├── agent/          # 核心 Agent 循环与子 Agent 管理
├── tools/          # 工具实现（read、write、edit、glob、grep、bash）
├── skills/         # Skill 发现、路由与执行
├── memory/         # 自进化记忆系统
├── context/        # 上下文压缩与缓存管理
├── permissions/    # 权限检查与安全审查
├── config/         # 分层配置加载
├── cli.py          # CLI 入口
├── repl.py         # 交互式 REPL
└── bootstrap.py    # 组件装配
```
