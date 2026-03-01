# execution

Voice-driven agent that connects your microphone to the browser via the OpenAI Realtime API.

## How it works

1. Captures PCM-16 audio from your microphone using `sounddevice`
2. Streams audio to the OpenAI Realtime API over WebSocket
3. The model transcribes speech, reasons, and issues tool calls
4. Tool calls are routed to `ami-browser` via MCP (Model Context Protocol)
5. Results are sent back to the model, which responds with synthesized speech

A Tkinter overlay displays live transcription and an audio waveform on top of the Chrome window.

## Requirements

- macOS recommended (overlay auto-positioning over Chrome uses AppleScript; on other platforms the overlay works but stays at a fixed position)
- A working microphone
- `OPENAI_API_KEY` set in your `.env` file

## Usage

```bash
uv sync
uv run python audio_ami.py
```
