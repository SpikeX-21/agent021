# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HelloAgents is an educational AI agent framework that teaches progressive agent building. The codebase demonstrates how to build AI coding agents from a simple loop (s01) to a full-featured system (s_full) with subagents, skills, task management, and team coordination.

## Architecture

### Core Pattern
The fundamental agent pattern implemented across all sessions:

```python
while stop_reason == "tool_use":
    response = LLM(messages, tools)
    execute tools
    append results
```

### Directory Structure

- **agents/** - Harness implementations for each learning session (s01-s12) and `s_full.py` (complete reference)
- **tools/** - Native tool system with Tool base class, ToolRegistry, and built-in tools
- **skills/** - Domain knowledge modules (agent-builder, code-review, mcp-builder, pdf) loaded on-demand via `load_skill`
- **web/** - Next.js documentation frontend
- **tests/** - Smoke tests verifying agent scripts compile

### Key Components

**Tool System** (`tools/base.py`, `tools/registry.py`):
- Abstract `Tool` base class with `run()` and `get_parameters()` methods
- `ToolRegistry` for registering and executing tools
- Support for expandable tools via `@tool_action` decorator
- Schema generation for Claude Code function calling

**Agent Sessions** (`agents/s01.py` through `agents/s_full.py`):
- Each session adds one new concept progressively
- `s_full.py` combines all mechanisms: todos, subagents, skills, file tasks, background tasks, messaging, teammates
- Each agent file is self-contained and runnable

**Skills** (`skills/*/SKILL.md`):
- Markdown files with YAML frontmatter (name, description)
- Loaded on-demand via `load_skill` tool
- Provides domain expertise without bloating system prompt

## Development Commands

### Python Environment
```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file (required)
cp .env.example .env
# Edit .env with ANTHROPIC_API_KEY and MODEL_ID
```

### Running Agents
```bash
# Run the full reference agent (interactive REPL)
python agents/s_full.py

# Run specific session agent
python agents/s01_agent_loop.py

# Exit REPL with: q, exit, or Ctrl+C
```

### Testing
```bash
# Run smoke tests (verifies agents compile)
pytest tests/

# Run specific test
pytest tests/test_agents_smoke.py -v
```

### Web Frontend
```bash
cd web

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

## Configuration

Required environment variables in `.env`:
- `ANTHROPIC_API_KEY` - Your API key
- `MODEL_ID` - Model to use (e.g., `claude-sonnet-4-6`)
- `ANTHROPIC_BASE_URL` (optional) - For compatible providers (MiniMax, GLM, Kimi, DeepSeek)

## Agent Session Progression

| Session | Concept Added |
|---------|--------------|
| s01 | Basic agent loop |
| s02 | Tool dispatch |
| s03 | Todo tracking |
| s04 | Subagents |
| s05 | Skills system |
| s06 | Compression |
| s07 | File-based tasks |
| s08 | Background tasks |
| s09 | Teammates & messaging |
| s10 | Shutdown & plan approval |
| s11 | Auto-claim tasks |
| s12 | Worktree isolation |
| s_full | All mechanisms combined |

## Working with This Codebase

- Each agent file is self-contained - changes to one don't affect others
- `s_full.py` is the production-ready reference implementation
- Skills are loaded by name - reference existing skills when building new ones
- Tools support both direct registration and expandable patterns
- The web frontend uses Next.js 16 with App Router and Tailwind CSS v4
