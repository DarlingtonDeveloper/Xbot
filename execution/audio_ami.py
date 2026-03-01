import asyncio
import base64
import json
import os
import subprocess
import sys
import threading

import customtkinter
from TkVisualizer import TkAudioVisualizer
import sounddevice as sd
import websockets
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    sys.exit("Error: OPENAI_API_KEY environment variable is not set. "
             "Add it to your .env file or export it in your shell.")

REALTIME_MODEL = "gpt-4o-realtime-preview"
REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"

SAMPLE_RATE = 24000
CHANNELS = 1
DTYPE = "int16"
CHUNK_DURATION_MS = 100
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_DURATION_MS // 1000

AMI_BROWSER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "ami-browser", "cli.js"
)

SYSTEM_PROMPT = """You are a helpful AI assistant called Ami that can browse the web using browser tools. Always respond in English only.

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

### ami_execute
Execute a saved tool for the current site. Parameters go in "args", NOT "params".
Example: {"toolName": "search-google", "args": {"query": "cats"}}
WRONG: {"toolName": "search-google", "params": {"query": "cats"}}

## Workflow
1. Use browser_navigate to go to a page
2. Use browser_snapshot to see what's on the page and get element refs
3. Use browser_fallback or ami_execute to interact with elements
4. Always take a snapshot after actions to see the result

## Important: Tool creation ordering
When no saved tools exist for a site, ALWAYS complete the user's task first using browser_fallback.
Only create configs and tools (add_create-config, add_tool) AFTER you have finished the action and verified the result with a snapshot."""

# Shared state between threads
VERBOSE = True

current_text = [""]
current_action = [""]
viz_ref = [None]
state_lock = threading.Lock()
browser_ready = threading.Event()


# ── Overlay ────────────────────────────────────────────────────────────────────

def get_chrome_bounds():
    """Returns (left, top, right, bottom) of the front Chrome window via AppleScript (macOS only)."""
    script = 'tell application "Google Chrome" to get bounds of front window'
    try:
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=1)
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            return tuple(int(x) for x in parts)  # left, top, right, bottom
    except Exception:
        pass
    return None


def run_overlay():
    H = 110
    root = customtkinter.CTk()
    root.overrideredirect(True)
    root.wm_attributes("-topmost", True)
    root.wm_attributes("-alpha", 0.9)
    root.configure(fg_color="black")
    root.geometry(f"520x{H}+100+100")

    # Text row: speech label + action label centered
    text_frame = customtkinter.CTkFrame(root, fg_color="black", height=28)
    text_frame.pack(fill="x", padx=10, pady=(6, 0))

    inner_frame = customtkinter.CTkFrame(text_frame, fg_color="black")
    inner_frame.pack(anchor="center")

    speech_label = customtkinter.CTkLabel(
        inner_frame, text="", font=("Courier", 14),
        text_color="#86efac", fg_color="black"
    )
    speech_label.pack(side="left")

    action_label = customtkinter.CTkLabel(
        inner_frame, text="", font=("Courier", 14, "italic"),
        text_color="white", fg_color="black"
    )
    action_label.pack(side="left")

    # Visualizer
    viz = TkAudioVisualizer(root, height=60)
    viz.pack(fill="both", expand=True, padx=8, pady=(4, 8))
    viz.start(external=True)
    viz_ref[0] = viz

    def sync_position():
        bounds = get_chrome_bounds()
        if bounds:
            left, top, right, bottom = bounds
            w = right - left
            x = left
            y = bottom - H
            root.geometry(f"{w}x{H}+{x}+{y}")
            root.wm_attributes("-topmost", True)
            root.lift()
            root.after(500, sync_position)
        else:
            root.destroy()

    def update_text():
        with state_lock:
            text = current_text[0]
            action = current_action[0]
        speech_label.configure(text=text)
        if VERBOSE and action:
            action_label.configure(text=f" -> {{{action}}}")
        else:
            action_label.configure(text="")
        root.after(50, update_text)

    root.withdraw()

    def show_when_ready():
        bounds = get_chrome_bounds()
        if bounds:
            sync_position()
            root.deiconify()
            update_text()
        else:
            root.after(200, show_when_ready)

    root.after(200, show_when_ready)
    root.mainloop()


# ── Async core ─────────────────────────────────────────────────────────────────

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
        # Feed visualizer
        if viz_ref[0]:
            viz_ref[0].feed(chunk)
        audio_b64 = base64.b64encode(chunk).decode("ascii")
        event = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64,
        }
        await ws.send(json.dumps(event))


async def audio_receiver(ws, mcp_session: ClientSession):
    """Listen for WebSocket events: handle tool calls, print transcripts."""
    pending_calls = {}

    async for raw_msg in ws:
        event = json.loads(raw_msg)
        event_type = event.get("type", "")

        # --- Transcripts ---
        if event_type == "conversation.item.input_audio_transcription.completed":
            transcript = event.get("transcript", "").strip()
            if transcript:
                print(f"\nYou: {transcript}")
                with state_lock:
                    current_text[0] = transcript
                    current_action[0] = ""

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

            if not name and call_id in pending_calls:
                name = pending_calls[call_id].get("name", "")

            pending_calls.pop(call_id, None)

            print(f"\n  [Tool: {name}]")
            with state_lock:
                current_action[0] = name

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
            pass

        elif event_type == "error":
            err = event.get("error", {})
            print(f"\n[API Error] {err.get('type', 'unknown')}: {err.get('message', '')}")

        elif event_type == "session.created":
            print("Session created.")

        elif event_type == "session.updated":
            print("Session configured.")


async def async_main():
    server_params = StdioServerParameters(
        command="node",
        args=[os.path.abspath(AMI_BROWSER_PATH)],
        env={**os.environ},
    )

    print("Starting ami-browser MCP server...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as mcp_session:
            await mcp_session.initialize()

            # Browser window is open — signal overlay to snap onto it immediately
            browser_ready.set()

            # Navigate to Google as the default home page
            print("Navigating to Google...")
            await mcp_session.call_tool("browser_navigate", {"url": "https://www.google.com"})
            print("Ready on Google.")

            # Discover MCP tools
            tools_result = await mcp_session.list_tools()
            realtime_tools = mcp_tools_to_realtime_functions(tools_result.tools)

            print(f"Connected! {len(realtime_tools)} tools available:")
            for t in realtime_tools:
                print(f"  - {t['name']}")

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
                max_size=2**24,
            ) as ws:
                # Wait for session.created
                raw = await ws.recv()
                event = json.loads(raw)
                if event.get("type") == "session.created":
                    print("Session created.")
                elif event.get("type") == "error":
                    err = event.get("error", {})
                    print(f"Connection error: {err}")
                    return
                else:
                    print(f"Unexpected first event: {json.dumps(event, indent=2)}")

                # Configure the session
                session_config = {
                    "type": "session.update",
                    "session": {
                        "modalities": ["text"],
                        "instructions": SYSTEM_PROMPT,
                        "tools": realtime_tools,
                        "input_audio_format": "pcm16",
                        "input_audio_transcription": {
                            "model": "whisper-1",
                            "language": "en",
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
                print("\nAudio Ami ready.\n", flush=True)

                # Run sender and receiver concurrently
                sender_task = asyncio.create_task(audio_sender(ws, audio_queue))
                receiver_task = asyncio.create_task(
                    audio_receiver(ws, mcp_session)
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
                    print("Goodbye!")


# ── Entry point ────────────────────────────────────────────────────────────────

threading.Thread(target=lambda: asyncio.run(async_main()), daemon=True).start()
browser_ready.wait()  # block until MCP server is ready
run_overlay()  # tkinter must run on the main thread
