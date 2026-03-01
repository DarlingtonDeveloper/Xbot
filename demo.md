# Ami - 2-Minute Demo Script

## Setup Before Demo
- Chrome open with Ami overlay visible at bottom
- Terminal running `audio_ami.py` (connected to MCP server)
- Database pre-loaded with 1-2 saved tool configs (e.g., Google Search)
- One fresh domain with NO saved tools (e.g., Amazon) to show the learning flow

---

## [0:00 - 0:20] Hook — The Problem is Real

**[Speaker, camera on face or slide]**

Imagine you can't move your hands. You can't scroll, click, or type.     

For millions of people around the world living with paralysis or muscular disease, the internet, the most powerful tool ever built, is locked behind a mouse and keyboard.

**[Cut to screen showing Ami overlay on Chrome]**

> "This is Ami. A voice-controlled AI browser that navigates the web for you — and gets smarter every time you use it."

---

## [0:20 - 0:55] Demo Part 1 — Seamless Voice Browsing (Cold Start)

**[Screen recording with mic audio]**

> "Let me show you. I've never visited X on Ami before — this is a cold start."

**User says:** *"Go to X and post "hi from Ami browser""*

**[Show on screen:]**
1. Ami navigates to X.com (Playwright browser launches/navigates)
2. Takes an accessibility snapshot of the page
3. Identifies the post bar, types "hi from Ami browser", submits

> "Ami understood my intent, navigated the site, wrote the post, and posted it to X - all from my voice. No hands required."

**[Pause briefly to let the result sink in]**

---

## [0:55 - 1:25] Demo Part 2 — Tool Storage (The Speed Difference)

> "But here's what makes Ami different from every other voice assistant. Watch what happens when I go to X again."

**User says:** *"Go to X and post "We love Mistral""*

**[Show on screen:]**
1. Ami recognizes it already has a saved tool for X posting
2. Calls `ami_execute` directly — no snapshot, no reasoning, no selector hunting
3. Results return almost instantly

> "That was 10x faster and used 90% fewer tokens. On the first visit, Ami learned the page structure — the search box, the submit button, where results live — and saved it as a reusable tool. Now every future search is a single function call."

**[Optional: briefly flash a side-by-side token comparison graphic]**
- First visit: ~44KB of tokens, multiple round trips
- Saved tool: ~5KB, one call

---

## [1:25 - 1:50] Demo Part 3 — Memory Layer (Semantic Retrieval)

> "And Ami remembers what matters to you."

**User says:** *"Find me some news to read."*

**[Show on screen:]**
1. Ami doesn't have an exact URL or tool name match
2. Semantic search finds the "news" config from earlier
3. Executes the saved website config with the new query

> "I didn't say 'BBC'.' Ami used semantic memory to connect my intent to a site I've used before. The more you use Ami, the faster and smarters it gets — it builds a personalized map of YOUR internet."

---

## [1:50 - 2:00] Close

> "Ami doesn't just browse the web for you. It learns how YOU use the web — and makes it faster every single time. Voice in, answers out. No hands needed."

**[Ami overlay pulses with audio visualization as the speaker finishes]**

---

## Demo Tips
- **Keep the browser visible the whole time** — the audience should see real pages loading
- **Don't script the exact voice commands** — slight natural variation makes it feel authentic
- **If a tool call is slow**, narrate what's happening: "Ami is reading the page structure right now"
- **Have a backup recording** in case of live demo issues — screen-record a clean run beforehand
