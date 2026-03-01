# MCP Two-Folder Architecture

## Architecture

```
~/Desktop/
  friend-mcp/          ← friend's folder (MCP server)
    server.py
    pyproject.toml
  jarvisicito/         ← your folder (client + your logic)
    execution/
      audio_ami.py
      db.py
      TkVisualizer.py
      overlay.js
```

---

## Option 1: Claude Desktop Config (simplest, no code changes)

Add the friend's server to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "friend-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/friend-mcp", "python", "server.py"]
    }
  }
}
```

Claude Desktop will auto-spawn it. Your folder stays separate.

---

## Option 2: Connect Programmatically (recommended)

In `audio_ami.py`, point `StdioServerParameters` at the friend's folder:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

FRIEND_MCP_PATH = "/path/to/friend-mcp"

server_params = StdioServerParameters(
    command="uv",
    args=["run", "python", "server.py"],
    cwd=FRIEND_MCP_PATH,   # tells it where to run from
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
```

Spawns the friend's server as a subprocess — no install needed on your side.

### How it works with OpenAI Realtime

OpenAI Realtime and MCP operate at separate layers:

```
Your voice
    ↓
OpenAI Realtime (gpt-4o-realtime-preview)
    → transcribes speech, reasons, decides to call a tool
    ↓
Your code receives the function call event
    → calls mcp_session.call_tool(name, args)
    ↓
Friend's MCP server executes the tool
    → returns a result
    ↓
Result sent back to OpenAI as function_call_output
    ↓
OpenAI continues / speaks back
```

On startup your code calls `list_tools()` on the MCP server and forwards the
tool list to OpenAI — OpenAI uses tool names and descriptions to decide when
to call each one. The implementation inside the MCP server is invisible to OpenAI.

---

## Option 3: HTTP/SSE (for different machines)

Friend runs their server with a port exposed:

```bash
# in friend-mcp/
uv run python server.py --port 8000
```

You connect via SSE transport:

```python
from mcp.client.sse import sse_client

async with sse_client("http://localhost:8000/sse") as (read, write):
    ...
```

---

## Recommendation

Start with **Option 2** (stdio, `cwd` pointing to friend's folder):
- Zero-config for your friend
- Works without a pre-running server process
- Both folders stay completely independent

Upgrade to **Option 3** when you need network access across different machines.
