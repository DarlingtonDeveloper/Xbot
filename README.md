<p align="center">
  <img src="./ami.jpg" alt="Ami" width="200" />
</p>

<h1 align="center">Ami</h1>

<p align="center">A voice-controlled AI agent that browses the web for you.</p>

---

## Modules

### ami-browser

An MCP server for browser automation built on [Playwright](https://playwright.dev). Exposes browser tools (navigate, snapshot, click, type, etc.) to any LLM via the [Model Context Protocol](https://modelcontextprotocol.io/).

### execution

A real-time audio interface powered by OpenAI's GPT-4o Realtime API. Streams your voice to the model, which decides when to use browser tools via MCP. Includes a Tkinter overlay that shows live transcription and audio visualization.

## Quick Start

```bash
# Install browser dependencies
cd ami-browser
npm install
npx playwright install

# Install Python dependencies
cd ../execution
uv sync
```

## Usage

```bash
cd execution
uv run python audio_ami.py
```

## License

Apache 2.0
