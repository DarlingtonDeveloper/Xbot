<p align="center">
  <img src="./ami.jpg" alt="Ami" width="200" />
</p>

<h1 align="center">Ami</h1>

<p align="center">A voice-controlled AI agent that browses the web for you.</p>

---

## Overview

Ami consists of two modules:

- **ami-browser** — An MCP server that exposes browser tools (navigate, snapshot, click, type, etc.) to any LLM via the [Model Context Protocol](https://modelcontextprotocol.io/). Built on [Playwright](https://playwright.dev).
- **execution** — A real-time audio interface powered by the Mistral Realtime API. Streams your voice to the model, which decides when to use browser tools via MCP. Includes a Tkinter overlay for live transcription and audio visualization.

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

### 3. Install ami-browser

```bash
cd ami-browser
npm install
npx playwright install
```

Create a `.env` file in `ami-browser/` with your database connection:

```
DATABASE_URL=postgresql://user:password@host:5432/database
```

### 4. Install execution

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

This package is **not published to npm**, so you cannot use `npx ami-browser`. Instead, point your MCP client to the local CLI entry point using `node`:

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

You can also pass options after `cli.js`:

```json
{
  "mcpServers": {
    "ami-browser": {
      "command": "node",
      "args": [
        "/absolute/path/to/ami/ami-browser/cli.js",
        "--headless"
      ]
    }
  }
}
```

Available CLI options:

- `--browser <browser>` — Browser to use (`chrome`, `firefox`, `webkit`, `chromium`, `msedge`)
- `--headless` — Run in headless mode
- `--config <path>` — Path to configuration file

## License

Apache 2.0
