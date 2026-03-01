import tkinter as tk
import random
import threading
import struct
import math

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False


class TkAudioVisualizer(tk.Frame):
    def __init__(self,
                 master: any,
                 gradient: list = ["#86efac", "#4ade80"],
                 bar_color: str = "black",
                 bar_width: int = 7,
                 **kwargs):

        tk.Frame.__init__(self, master)
        self.viz = draw_bars(self, gradient[0], gradient[1], bar_width, bar_color, relief="sunken", **kwargs)
        self.viz.pack(fill="both", expand=True)

    def start(self, external=False):
        """start the visualizer. Pass external=True to skip opening a mic stream."""
        if not self.viz._running:
            self.viz._running = True
            if not external:
                self.viz._start_mic()
            self.viz.update()

    def feed(self, data: bytes):
        """Feed raw PCM16 audio data from an external source."""
        self.viz.feed(data)

    def stop(self):
        """stop the visualizer"""
        self.viz._running = False


class draw_bars(tk.Canvas):
    """A canvas that draws audio-reactive bars from the microphone"""
    def __init__(self, parent, color1, color2, bar_width, bar_color, **kwargs):
        tk.Canvas.__init__(self, parent, bg=bar_color, bd=0, highlightthickness=0, **kwargs)
        self._color1 = color1
        self._color2 = color2
        self._bar_width = bar_width
        self._running = False
        self._amplitude = 0.0   # smoothed 0.0–1.0
        self._pa = None
        self._mic_stream = None
        self.after(100, self._draw_gradient)
        self.bind("<Configure>", lambda e: self._draw_gradient() if not self._running else None)

    # ── Microphone ────────────────────────────────────────────────────────────

    def _start_mic(self):
        if not PYAUDIO_AVAILABLE:
            return
        self._pa = pyaudio.PyAudio()
        self._mic_stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=512,
            stream_callback=self._mic_callback,
        )
        self._mic_stream.start_stream()

    def feed(self, data: bytes):
        samples = struct.unpack(f'{len(data) // 2}h', data)
        rms = math.sqrt(sum(s * s for s in samples) / len(samples))
        raw = min(1.0, rms / 1500.0)
        alpha = 0.6 if raw > self._amplitude else 0.15
        self._amplitude = alpha * raw + (1 - alpha) * self._amplitude

    def _mic_callback(self, in_data, frame_count, time_info, status):
        samples = struct.unpack(f'{len(in_data) // 2}h', in_data)
        rms = math.sqrt(sum(s * s for s in samples) / len(samples))
        # Normalize: quiet ~100 RMS, loud speech ~4000 RMS
        raw = min(1.0, rms / 1500.0)
        # Exponential smoothing — fast attack, slow decay
        alpha = 0.6 if raw > self._amplitude else 0.15
        self._amplitude = alpha * raw + (1 - alpha) * self._amplitude
        return (None, pyaudio.paContinue)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw_gradient(self, event=None):
        self.delete("gradient")
        width = self.winfo_width()
        height = self.winfo_height()
        limit = width + 10

        (r1, g1, b1) = self.winfo_rgb(self._color1)
        (r2, g2, b2) = self.winfo_rgb(self._color2)
        r_ratio = float(r2 - r1) / limit
        g_ratio = float(g2 - g1) / limit
        b_ratio = float(b2 - b1) / limit

        amp = self._amplitude  # 0.0–1.0

        for i in range(0, limit, self._bar_width):
            if self._running:
                # Each bar gets random variation around the current amplitude
                variation = random.uniform(0.4, 1.0)
                bar_height = max(2, int(amp * height * 0.9 * variation))
            else:
                bar_height = 0

            nr = int(r1 + (r_ratio * i))
            ng = int(g1 + (g_ratio * i))
            nb = int(b1 + (b_ratio * i))
            color = "#%4.4x%4.4x%4.4x" % (nr, ng, nb)
            self.create_line(i, height, i, height - bar_height,
                             tags=("gradient",), width=self._bar_width, fill=color)

        self.lower("gradient")

        if self._running:
            self.after(50, self._draw_gradient)

    def update(self):
        self._draw_gradient()
