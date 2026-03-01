<p align="center">
  <img src="./ami.jpg" alt="Ami" width="200" />
</p>

<h1 align="center">Ami</h1>

<p align="center">A voice-controlled AI agent that browses the web for you.</p>

---

## How It Works

### ami-browser: Smart Browser Automation

ami-browser is an [MCP](https://modelcontextprotocol.io/) server that sits on top of [Playwright](https://playwright.dev) and adds a layer of **stored tools and memory**. Most things we do on the web are things we've done before: searching, adding to cart, checking out. ami-browser takes advantage of this by learning and reusing procedures.

When you navigate to a site:

1. **Known site**: ami-browser looks up the domain and URL pattern in its database. If it finds stored tools (e.g. `search-products`, `add-to-cart`), they're immediately available. The LLM calls them by name with parameters, and ami-browser translates them into Playwright actions. Fast, cheap, no page parsing needed.

2. **New site**: No stored tools exist yet, so ami-browser falls back to raw Playwright tools (snapshot, click, type). As the LLM explores the page, ami-browser nudges it to save what it learns as reusable tools (CSS selectors, form fields, submit actions, and result extraction) so the next visit is instant.

This means ami-browser gets smarter over time. The first visit to a site is exploratory. Every visit after that reuses stored procedures, saving tokens, time, and money.

### execution: Voice-Driven Agent

The execution module connects your voice to the browser through a real-time audio pipeline:

```
🎤 You speak
 ↓  Microphone captures PCM audio, streams to API
🧠 OpenAI Realtime API (gpt-4o)
 ↓  Transcribes speech, reasons, decides which tools to call
🔧 Tool calls routed to ami-browser via MCP
 ↓  ami-browser executes browser actions (stored or fallback)
📋 Results sent back to the model
 ↓  Model synthesizes a spoken response
🔊 You hear the answer
```

The agent uses server-side voice activity detection to know when you've finished speaking, runs any necessary browser tools, and responds in natural speech. A Tkinter overlay shows live transcription and an audio waveform on top of the browser window.

## Project Structure

```
ami/
├── ami-browser/    # MCP server (Node.js)
├── execution/      # Voice agent (Python)
└── supabase/       # Database migrations & config
```

## Prerequisites

- [Node.js](https://nodejs.org/) >= 18
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- A PostgreSQL database with the [pgvector](https://github.com/pgvector/pgvector) extension
- **macOS** recommended for the voice agent (the overlay uses AppleScript to auto-position over Chrome; on other platforms the overlay still works but won't track the browser window)

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/felofix/ami.git
cd ami
```

### 2. Set up the database

Run the migration against your PostgreSQL database:

```bash
psql $DATABASE_URL -f supabase/migrations/0001_init_schema.sql
```

Or if you use the [Supabase CLI](https://supabase.com/docs/guides/local-development/cli):

```bash
supabase db push
```

### 3. Configure environment

Copy the example and fill in your values:

```bash
cp .env.example .env
```

Required variables (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OPENAI_API_KEY` | OpenAI API key (for the voice agent) |
| `DATABASE_SSL` | Set to `true` to enable SSL for database connections (optional) |

### 4. Install ami-browser

```bash
cd ami-browser
npm install
npx playwright install
```

### 5. Install execution

```bash
cd ../execution
uv sync
```

## Usage

### Running the voice agent

```bash
cd execution
uv run python audio_ami.py
```

### Using ami-browser as an MCP server

Point your MCP client to the local CLI entry point using `node`:

```json
{
  "mcpServers": {
    "ami-browser": {
      "command": "node",
      "args": ["/absolute/path/to/ami/ami-browser/cli.js"]
    }
  }
}
```

Replace `/absolute/path/to/ami` with the actual path on your machine.

Available CLI options:

- `--browser <browser>` — Browser to use (`chrome`, `firefox`, `webkit`, `chromium`, `msedge`)
- `--headless` — Run in headless mode
- `--config <path>` — Path to configuration file

## License

Apache 2.0
