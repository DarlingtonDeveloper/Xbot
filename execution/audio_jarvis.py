import asyncio
import base64
import json
import os
import subprocess
import threading

import customtkinter
from TkVisualizer import TkAudioVisualizer
import pyaudio
from dotenv import load_dotenv
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


load_dotenv()
client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

SAMPLE_RATE = 24000
CHUNK_MS = 480
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_MS / 1000)

# Shared state between threads
VERBOSE = True

current_text = [""]
current_action = [""]
viz_ref = [None]
state_lock = threading.Lock()
browser_ready = threading.Event()


# ── Overlay ────────────────────────────────────────────────────────────────────

def get_chrome_bounds():
    """Returns (left, top, right, bottom) of the front Chrome window via AppleScript."""
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
        sync_position()
        root.deiconify()
        update_text()

    root.after(500, show_when_ready)
    root.mainloop()


# ── Async core ─────────────────────────────────────────────────────────────────

def mcp_to_realtime_tool(tool):
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description or "",
        "parameters": tool.inputSchema,
    }


async def async_main():
    server_params = StdioServerParameters(
        command="npx",
        args=["@playwright/mcp@latest", "--browser", "chrome"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as mcp_session:
            await mcp_session.initialize()

            tools_result = await mcp_session.list_tools()
            mcp_tools = [mcp_to_realtime_tool(t) for t in tools_result.tools]

            await mcp_session.call_tool("browser_navigate", {"url": "about:blank"})
            browser_ready.set()

            pa = pyaudio.PyAudio()
            mic = pa.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
                          input=True, frames_per_buffer=CHUNK_SAMPLES)
            speaker = pa.open(format=pyaudio.paInt16, channels=1, rate=SAMPLE_RATE,
                              output=True, frames_per_buffer=CHUNK_SAMPLES)
            loop = asyncio.get_running_loop()

            async with client.beta.realtime.connect(model="gpt-4o-realtime-preview") as conn:
                await conn.session.update(session={
                    "instructions": "You are a browser assistant. When looking at retrieved tools you need to balance description matching with number of times visiting the website.",
                    "modalities": ["text", "audio"],
                    "voice": "alloy",
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "gpt-4o-mini-transcribe", "language": "en"},
                    "tools": mcp_tools,
                    "tool_choice": "auto",
                    "turn_detection": {
                        "type": "server_vad",
                        "silence_duration_ms": 200,
                        "prefix_padding_ms": 100,
                    },
                })
                print("Audio Jarvis ready.\n", flush=True)

                async def send_audio():
                    try:
                        while True:
                            data = await loop.run_in_executor(None, mic.read, CHUNK_SAMPLES, False)
                            if viz_ref[0]:
                                viz_ref[0].feed(data)
                            await conn.input_audio_buffer.append(
                                audio=base64.b64encode(data).decode()
                            )
                    except asyncio.CancelledError:
                        pass

                send_task = asyncio.create_task(send_audio())

                try:
                    async for event in conn:

                        # User speech → text
                        if event.type == "conversation.item.input_audio_transcription.completed":
                            text = event.transcript.strip()
                            print(f"You: {text}\n", flush=True)
                            with state_lock:
                                current_text[0] = text
                                current_action[0] = ""

                        # Tool call from model
                        elif event.type == "response.function_call_arguments.done":
                            name = event.name
                            args = json.loads(event.arguments)
                            print(f"[Tool Call] {name} {args}", flush=True)
                            with state_lock:
                                current_action[0] = name

                            result = await mcp_session.call_tool(name, args)

                            content = "\n".join(
                                b.text for b in result.content if hasattr(b, "text")
                            )

                            await conn.conversation.item.create(item={
                                "type": "function_call_output",
                                "call_id": event.call_id,
                                "output": content or "Done",
                            })
                            await conn.response.create()

                        elif event.type == "error":
                            print(f"Error: {event.error}", flush=True)

                except KeyboardInterrupt:
                    print("\nBye.")
                finally:
                    send_task.cancel()
                    mic.stop_stream()
                    mic.close()
                    speaker.stop_stream()
                    speaker.close()
                    pa.terminate()


# ── Entry point ────────────────────────────────────────────────────────────────

threading.Thread(target=lambda: asyncio.run(async_main()), daemon=True).start()
browser_ready.wait()  # block until Chromium is fully open
run_overlay()  # tkinter must run on the main thread
