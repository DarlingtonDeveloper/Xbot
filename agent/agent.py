import os
import sys
import json
import asyncio
import base64
import numpy as np
import sounddevice as sd
import websockets
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REALTIME_MODEL = "gpt-4o-realtime-preview"
REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"

SAMPLE_RATE = 24000
CHANNELS = 1
DTYPE = "int16"
CHUNK_DURATION_MS = 100
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_DURATION_MS // 1000

PARROT_BROWSER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "parrot-browser", "cli.js"
)

SYSTEM_PROMPT = """You are a helpful AI assistant that can browse the web using browser tools.

## Tool usage rules

### browser_navigate
Navigate to a URL. Example arguments: {"url": "https://example.com"}

### browser_snapshot
Take a snapshot to see page content and get element refs. Call with no arguments: {}

### browser_fallback
Gateway to Playwright tools. Arguments to the underlying tool MUST go inside the "arguments" object.
Examples:
- Click: {"tool": "browser_click", "arguments": {"ref": "e12"}}
- Type: {"tool": "browser_type", "arguments": {"ref": "e12", "text": "hello"}}
- Press key: {"tool": "browser_press_key", "arguments": {"key": "Enter"}}
- Hover: {"tool": "browser_hover", "arguments": {"ref": "e12"}}
WRONG: {"tool": "browser_type", "ref": "e12", "text": "hello"} — ref/text must be inside "arguments"!

### parrot_execute
Execute a saved tool for the current site. Parameters go in "args", NOT "params".
Example: {"toolName": "search-google", "args": {"query": "cats"}}
WRONG: {"toolName": "search-google", "params": {"query": "cats"}}

## Workflow
1. Use browser_navigate to go to a page
2. Use browser_snapshot to see what's on the page and get element refs
3. Use browser_fallback or parrot_execute to interact with elements
4. Always take a snapshot after actions to see the result"""


def mcp_tools_to_realtime_functions(tools):
    """Convert MCP tool schemas to OpenAI Realtime API function format."""
    functions = []
    for tool in tools:
        func = {
            "type": "function",
            "name": tool.name,
            "description": tool.description or "",
        }
        if tool.inputSchema:
            func["parameters"] = tool.inputSchema
        else:
            func["parameters"] = {"type": "object", "properties": {}}
        functions.append(func)
    return functions


async def audio_sender(ws, audio_queue: asyncio.Queue):
    """Read audio chunks from queue, base64-encode and send to Realtime API."""
    while True:
        chunk = await audio_queue.get()
        if chunk is None:
            break
        audio_b64 = base64.b64encode(chunk).decode("ascii")
        event = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64,
        }
        await ws.send(json.dumps(event))


async def audio_receiver(ws, mcp_session: ClientSession, output_stream):
    """Listen for WebSocket events: play audio, handle tool calls, print transcripts."""
    # Track in-progress function calls by call_id
    pending_calls = {}

    async for raw_msg in ws:
        event = json.loads(raw_msg)
        event_type = event.get("type", "")

        # --- Audio playback ---
        if event_type == "response.audio.delta":
            audio_bytes = base64.b64decode(event["delta"])
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16)
            output_stream.write(audio_np)

        # --- Transcripts ---
        elif event_type == "conversation.item.input_audio_transcription.completed":
            transcript = event.get("transcript", "").strip()
            if transcript:
                print(f"\nYou: {transcript}")

        elif event_type == "response.audio_transcript.done":
            transcript = event.get("transcript", "").strip()
            if transcript:
                print(f"\nAssistant: {transcript}")

        # --- Function calling ---
        elif event_type == "response.function_call_arguments.delta":
            call_id = event.get("call_id", "")
            delta = event.get("delta", "")
            if call_id not in pending_calls:
                pending_calls[call_id] = {
                    "arguments": "",
                    "name": event.get("name", ""),
                }
            pending_calls[call_id]["arguments"] += delta

        elif event_type == "response.function_call_arguments.done":
            call_id = event.get("call_id", "")
            name = event.get("name", "")
            arguments_str = event.get("arguments", "")

            # Also check pending_calls for name if not in this event
            if not name and call_id in pending_calls:
                name = pending_calls[call_id].get("name", "")

            # Clean up pending
            pending_calls.pop(call_id, None)

            print(f"\n  [Tool: {name}]")
            try:
                tool_args = json.loads(arguments_str) if arguments_str else {}
                print(f"  [Args: {json.dumps(tool_args, indent=2)}]")
            except json.JSONDecodeError:
                tool_args = {}
                print(f"  [Args (raw): {arguments_str}]")

            # Execute MCP tool
            try:
                result = await mcp_session.call_tool(name, tool_args)
                result_text = ""
                for content in result.content:
                    if hasattr(content, "text"):
                        result_text += content.text
                    elif hasattr(content, "data"):
                        result_text += f"[image: {content.mimeType}]"

                if len(result_text) > 20000:
                    result_text = result_text[:20000] + "\n... (truncated)"

                print(
                    f"  [Result: {result_text[:200]}{'...' if len(result_text) > 200 else ''}]"
                )
            except Exception as e:
                result_text = f"Error: {e}"
                print(f"  [Error: {e}]")

            # Send function call output back to the model
            output_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": result_text,
                },
            }
            await ws.send(json.dumps(output_event))

            # Ask the model to continue with the tool result
            await ws.send(json.dumps({"type": "response.create"}))

        elif event_type == "response.done":
            pass  # Turn complete

        elif event_type == "error":
            err = event.get("error", {})
            print(f"\n[API Error] {err.get('type', 'unknown')}: {err.get('message', '')}")

        elif event_type == "session.created":
            print("Session created.")

        elif event_type == "session.updated":
            print("Session configured.")


async def main():
    server_params = StdioServerParameters(
        command="node",
        args=[os.path.abspath(PARROT_BROWSER_PATH)],
    )

    print("Starting parrot-browser MCP server...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as mcp_session:
            await mcp_session.initialize()

            # Discover MCP tools
            tools_result = await mcp_session.list_tools()
            realtime_tools = mcp_tools_to_realtime_functions(tools_result.tools)

            print(f"Connected! {len(realtime_tools)} tools available:")
            for t in realtime_tools:
                print(f"  - {t['name']}")

            # Open audio output stream
            output_stream = sd.OutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
            )
            output_stream.start()

            # Audio input queue
            audio_queue: asyncio.Queue = asyncio.Queue()

            # Mic callback: push raw PCM-16 bytes into the async queue
            loop = asyncio.get_event_loop()

            def mic_callback(indata, frames, time_info, status):
                if status:
                    print(f"[Mic status: {status}]", file=sys.stderr)
                pcm_bytes = indata.copy().tobytes()
                loop.call_soon_threadsafe(audio_queue.put_nowait, pcm_bytes)

            input_stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=CHUNK_SAMPLES,
                callback=mic_callback,
            )

            # Connect to OpenAI Realtime API
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1",
            }

            print("Connecting to OpenAI Realtime API...")

            async with websockets.connect(
                REALTIME_URL,
                additional_headers=headers,
                max_size=2**24,  # 16 MB max message size
            ) as ws:
                # Wait for session.created
                raw = await ws.recv()
                event = json.loads(raw)
                if event.get("type") == "session.created":
                    print("Session created.")
                else:
                    print(f"Unexpected first event: {event.get('type')}")

                # Configure the session
                session_config = {
                    "type": "session.update",
                    "session": {
                        "modalities": ["text", "audio"],
                        "instructions": SYSTEM_PROMPT,
                        "tools": realtime_tools,
                        "input_audio_format": "pcm16",
                        "output_audio_format": "pcm16",
                        "input_audio_transcription": {
                            "model": "whisper-1",
                        },
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.5,
                            "prefix_padding_ms": 300,
                            "silence_duration_ms": 500,
                        },
                    },
                }
                await ws.send(json.dumps(session_config))

                # Start mic
                input_stream.start()
                print("\nListening... (speak into your microphone, Ctrl+C to exit)\n")

                # Run sender and receiver concurrently
                sender_task = asyncio.create_task(audio_sender(ws, audio_queue))
                receiver_task = asyncio.create_task(
                    audio_receiver(ws, mcp_session, output_stream)
                )

                try:
                    await asyncio.gather(sender_task, receiver_task)
                except (KeyboardInterrupt, asyncio.CancelledError):
                    pass
                finally:
                    print("\nShutting down...")
                    sender_task.cancel()
                    receiver_task.cancel()
                    input_stream.stop()
                    input_stream.close()
                    output_stream.stop()
                    output_stream.close()
                    print("Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
