# 🛡️ Vigil MCP Server

Model Context Protocol (MCP) server for **Vigil** — Automated Multi-Agent AI Code Review & Security Remediation Platform.

The Vigil MCP Server allows AI coding assistants (Claude Desktop, Cursor, Windsurf, Antigravity, etc.) to directly interact with Vigil's backend engine to perform automated security reviews, inspect findings, audit GitHub repositories, and trigger remediation scans.

---

## 🛠️ Available MCP Tools (8 Tools)

| Tool | Description | Parameters |
| :--- | :--- | :--- |
| `vigil_health_check` | Check operational status and database/redis connectivity of Vigil backend | None |
| `vigil_review_code` | Submit source code for multi-agent AST and LLM security analysis | `source_code` (str), `language` (`python` \| `javascript` \| `typescript`) |
| `vigil_get_findings` | Retrieve findings, metrics, and severity breakdown for a review run | `run_id` (str, UUID) |
| `vigil_list_repositories` | List connected GitHub repositories and their CI/CD status | None |
| `vigil_trigger_repo_review` | Trigger security scan on a connected GitHub repository | `repository_id` (str), `ref_type` (str), `ref_value` (str), `scope_mode` (`full_repo` \| `changed_files`) |
| `vigil_generate_patch` | Generate autonomous surgical unified diff remediation patch | `finding_id` (str, UUID) |
| `vigil_validate_patch` | Execute sandbox behavioral validation & test execution in gVisor | `patch_id` (str, UUID) |
| `vigil_get_agent_tree` | Fetch 14-stage multi-agent DAG execution tree, status nodes & timing | `run_id` (str, UUID) |

---

## 🚀 Installation & Local Setup

### 1. Install Package in Editable Mode
```bash
cd mcp-server
pip install -e .
```

### 2. Verify Import
```bash
python -c "from vigil_mcp import server; print('ok')"
```

---

## 🔍 Testing with MCP Inspector

Test and inspect the available tools interactively using the official MCP Inspector:

```bash
npx @modelcontextprotocol/inspector python -m vigil_mcp
```

This launches the web inspector UI (typically at `http://127.0.0.1:6274`) allowing you to test tool calls, inspect schemas, and view real-time responses.

---

## 🔌 Connecting to AI Clients

### 1. Claude Desktop
Add the following configuration to your `claude_desktop_config.json`:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "vigil": {
      "command": "python",
      "args": ["-m", "vigil_mcp"],
      "env": {
        "VIGIL_API_URL": "http://localhost:8000",
        "VIGIL_API_TOKEN": "<YOUR_JWT_ACCESS_TOKEN_IF_AUTHENTICATED>"
      }
    }
  }
}
```

### 2. Cursor IDE
Add to `.cursor/mcp.json` or configure in **Cursor Settings → Features → MCP**:

```json
{
  "mcpServers": {
    "vigil": {
      "command": "python",
      "args": ["-m", "vigil_mcp"],
      "env": {
        "VIGIL_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### 3. Antigravity / Gemini CLI
Add to `mcp_config.json`:

```json
{
  "mcpServers": {
    "vigil": {
      "command": "python",
      "args": ["-m", "vigil_mcp"],
      "env": {
        "VIGIL_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

---

## ⚙️ Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `VIGIL_API_URL` | Base URL of the running Vigil backend REST API | `http://localhost:8000` |
| `VIGIL_API_TOKEN` | Bearer JWT token for authenticated endpoints | *None (empty)* |
