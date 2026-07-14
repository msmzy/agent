# RepoPilot

AI Coding Agent inspired by Claude Code architecture. Built with raw Anthropic SDK, featuring skill routing, self-evolving memory, hierarchical context compression, centralized multi-agent collaboration, and permission security review.

## Architecture

The system is organized in three layers, from top to bottom:

**Interface Layer** — CLI / REPL (Typer + Rich) handles user interaction.

**Security Layer** — Permission Checker enforces deny-first rules and security review before any tool execution.

**Execution Layer** — Agent Loop (Query Loop + Tool Dispatch) coordinates five core modules:

- **Tools** — read, write, edit, glob, grep, bash
- **Skills** — loader, router, skill tool (two-stage routing with progressive loading)
- **Memory** — store, indexer, evolution engine (self-evolving knowledge base)
- **Context Manager** — token counter, cache, compressor (three-layer compression pipeline)
- **Sub-Agents** — spawn, parallel execution, restricted tool sets

## Key Technical Highlights

### 1. Skill Routing System (Skill分层路由)

Two-stage routing with progressive context loading:
- **Stage 1 - Recall**: Keyword + tag matching for fast candidate filtering
- **Stage 2 - Rerank**: LLM evaluates candidates using frontmatter only (no full body)
- **Progressive Loading**: Only YAML frontmatter scanned at startup; full skill body loaded on invocation
- Solves: retrieval noise, function overlap, token cost growth

### 2. Self-Evolving Memory (自进化记忆沉淀)

Closed-loop memory system: execution → reflection → extraction → categorized storage → index update → on-demand reuse
- **5 memory types**: user, feedback, project, reference, procedural
- **File-based storage**: Markdown files with YAML frontmatter + MEMORY.md index
- **TF-IDF retrieval**: Keyword matching with IDF weighting and recency bonus
- **Auto-reflection**: LLM analyzes conversations to extract reusable knowledge

### 3. Hierarchical Context Compression (分层上下文压缩)

Three-layer compression pipeline, cheapest first:
- **Layer 1 - Microcompact**: Truncate oversized tool outputs, keep only N recent complete results
- **Layer 2 - Context Collapse (70%)**: Fold old tool_call/tool_result pairs into one-line summaries
- **Layer 3 - Auto-compact (85%)**: LLM-generated structured summary, preserving system prompt and tool definitions

### 4. Centralized Multi-Agent Collaboration (中心化多Agent协作)

Central orchestrator pattern with controlled sub-agent execution:
- Sub-agents spawned as tool_calls (no control transfer)
- Independent context windows with restricted tool sets
- Parallel execution support via ThreadPoolExecutor
- Path boundary restrictions for security

### 5. Permission & Security Review (权限与安全审查)

Multi-layer security chain:
- **Rule Engine**: Deny-first semantics (deny always wins over allow)
- **Tool Classification**: read_only / write / dangerous
- **Bash Security**: Pattern matching for dangerous commands (rm -rf, sudo, curl|bash, etc.)
- **Prompt Injection Detection**: Regex patterns for instruction override, role hijacking, system tag injection
- **Path Traversal Detection**: Block access to sensitive system paths
- **Sandbox**: Working directory restrictions, sensitive env var filtering

## Tech Stack

- **LLM API** — `anthropic` SDK (tool use, streaming, prompt caching)
- **Data Model** — `pydantic`
- **CLI** — `typer`
- **Terminal UI** — `rich` (Markdown, Panel, Spinner)
- **REPL** — `prompt-toolkit` (history, auto-suggest)
- **Memory** — Markdown files + YAML frontmatter
- **Config** — JSON (hierarchical: global → project → local)

## Quick Start (从零开始运行)

### 1. 环境要求

- Python >= 3.10
- Anthropic API Key（支持 Claude 模型的 API 密钥）

### 2. 克隆并安装

```bash
git clone https://github.com/your-username/repopilot.git
cd repopilot

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

### 5. 使用

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
❯ 分析当前项目的目录结构
❯ 读取 main.py 并解释它的逻辑
❯ 找到所有包含 TODO 的文件
❯ /skills    # 查看可用的 Skill
❯ /usage     # 查看 token 消耗
❯ /exit      # 退出
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

### REPL Commands

- `/help` — Show available commands
- `/clear` — Clear conversation history
- `/usage` — Show token usage statistics
- `/mode` — Switch permission mode
- `/memory` — Show loaded memories
- `/skills` — List available skills
- `/exit` — Exit RepoPilot

## Configuration

Settings are loaded hierarchically (later layers override earlier ones):

1. `~/.repopilot/settings.json` (global)
2. `.repopilot/settings.json` (project)
3. `.repopilot/settings.local.json` (local, gitignored)

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

## Creating Custom Skills

Place a `SKILL.md` file in `.repopilot/skills/<skill-name>/`:

```markdown
---
name: my-skill
description: What this skill does
triggers:
  - /my-skill
  - keywords that activate it
tags:
  - category
applicable_when: When to use this skill
not_applicable_when: When to skip
---

# Instructions for the agent when this skill is invoked
...
```

## Testing

```bash
pip install -e ".[dev]"
pytest tests/
```

## Project Structure

```
repopilot/
├── agent/          # Core agent loop and sub-agent management
├── tools/          # Tool implementations (read, write, edit, glob, grep, bash)
├── skills/         # Skill discovery, routing, and execution
├── memory/         # Self-evolving memory system
├── context/        # Context compression and cache management
├── permissions/    # Permission checking and security review
├── config/         # Hierarchical configuration
├── cli.py          # CLI entry point
├── repl.py         # Interactive REPL
└── bootstrap.py    # Component wiring
```

## License

MIT
