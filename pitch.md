# Ami - 5-Minute Pitch Script

---

## [0:00 - 0:45] The Problem — The Internet Has an Accessibility Crisis

> "The internet is the most powerful tool humanity has ever built. It's how we shop, bank, learn, communicate, work. But for over 5 million Americans with paralysis — and tens of millions more with muscular diseases like ALS, muscular dystrophy, and multiple sclerosis — the internet is largely inaccessible."

> "Screen readers help with content, but they can't *act*. You still need hands to click a button, fill a form, or scroll through search results. Voice assistants like Siri and Alexa handle simple commands, but try booking a flight, comparing products, or filling out a medical form — they fall apart."

> "These aren't edge cases. These are daily necessities. And right now, millions of people need a human caregiver just to check their email."

> "We believe that's unacceptable."

---

## [0:45 - 1:30] The Solution — Meet Ami

> "Ami is a voice-controlled AI agent that browses the entire web for you. Not a simplified version. Not a special app. The real, full internet — any website, any page, any interaction."

> "You speak. Ami acts. It navigates to sites, reads content, fills forms, clicks buttons, and speaks the results back to you. It works on top of a real Chrome browser using Playwright, which means it works on every website — no special integrations, no developer cooperation needed."

**[Show brief visual/screenshot of Ami's Chrome overlay with audio visualization]**

> "But Ami isn't just a voice wrapper around a browser. We've built three technical innovations that make it fundamentally different from anything else out there."

---

## [1:30 - 2:15] Differentiator 1 — Seamless Browser Integration with Playwright MCP

> "First: seamless browser integration."

> "Ami is built on the Model Context Protocol — MCP — using Playwright as the browser engine. This gives us something no voice assistant has: full programmatic control over a real browser session."

> "Ami doesn't screenshot the page and guess. It reads the accessibility tree — the same structure screen readers use — which means it understands the page the way it was meant to be understood. It sees buttons, links, forms, headings — not pixels."

> "And because it's Playwright under the hood, it handles the hard stuff: SPAs that dynamically load content, redirects, shadow DOM, iframes. Ami can interact with any modern website — Gmail, Amazon, hospital portals, government forms — because it's controlling a real browser, not simulating one."

---

## [2:15 - 3:15] Differentiator 2 — Tool Storage That Reduces Cost and Increases Speed

> "Second — and this is our core innovation — tool storage."

> "Here's the problem with AI agents that browse the web: they're expensive and slow. Every time you ask an AI to search Amazon, it has to snapshot the page, reason about what it sees, find the right element, click it, snapshot again, reason again. That's tens of thousands of tokens per action. At scale, that's unsustainable."

> "Ami solves this by learning. The first time you visit a website, Ami browses it the traditional way — snapshots, reasoning, interaction. But as it works, it saves the workflow as a reusable tool: which selectors to target, which forms to fill, where the results live."

> "The second time? Ami skips all of that. It calls the saved tool directly — one function call, no snapshots, no reasoning overhead."

**[Show comparison graphic or state verbally:]**

> "In practice, this means:"
> - "First visit: 44,000 tokens, multiple round trips, several seconds"
> - "Every visit after: 5,000 tokens, one call, near instant"

> "That's a 90% reduction in cost and a dramatic speedup. And these tools are parameterized — a 'search products' tool works for any query. An 'open email' tool works for any inbox. Ami doesn't just memorize; it generalizes."

---

## [3:15 - 3:50] Differentiator 3 — Memory Layer with Semantic Retrieval

> "Third: semantic memory."

> "Ami remembers the websites you use and builds a personalized map of your internet. Every saved tool gets embedded — stored as a vector in a database. When you make a request, Ami doesn't just pattern-match on URLs. It searches semantically."

> "So if you say 'find me something to sit on,' Ami can connect that to a wheelchair cushion search you did on Amazon last week — even though you never said 'Amazon' or 'search.' It understands intent, not just keywords."

> "This means Ami gets meaningfully smarter with every session. Frequent sites are prioritized. Past workflows are instantly recalled. It's not starting from zero every time — it's building on everything you've done before."

---

## [3:50 - 4:30] Live Demo Moment / Impact

> "Let me show you what this looks like."

**[Run the key demo sequence — either live or pre-recorded:]**
1. Voice command → cold-start Amazon search (full browsing flow)
2. Second voice command → saved tool fires instantly (show the speed difference)
3. Ambiguous command → semantic retrieval finds the right workflow

> "That's the full loop. Voice in, answers out. And it gets faster every single time."

**[Pause. Let it land.]**

> "For someone with ALS who's losing motor function month by month, this isn't a convenience. It's independence. It's being able to order your own groceries, read your own email, manage your own finances — without waiting for someone else to move a mouse for you."

---

## [4:30 - 5:00] Close — Vision and Ask

> "Ami democratizes the internet for people who've been locked out of it. Not with a simplified interface or a walled garden — with the full, real web, controlled entirely by voice."

> "Our technical moat is the tool storage layer. Every interaction makes Ami faster, cheaper, and smarter. And because tools are saved per-domain, a community of users can contribute workflows — one person teaches Ami how to use a hospital portal, and every user after them benefits instantly."

> "We're building the accessibility layer the internet should have had from the start."

> "Thank you."

---

## Appendix: Audience Q&A Prep

**Q: How is this different from screen readers?**
> Screen readers are read-only — they narrate content but can't act. Ami reads AND acts: it fills forms, clicks buttons, submits searches, and extracts results.

**Q: How is this different from Siri/Alexa?**
> Voice assistants use pre-built integrations with specific apps. Ami works on ANY website with zero integration needed. It controls a real browser.

**Q: What about privacy?**
> Ami runs locally — your browser session stays on your machine. The tool storage database can be self-hosted. Voice processing uses OpenAI's Realtime API with standard data policies.

**Q: What's the token cost at scale?**
> With tool storage, recurring tasks cost ~90% fewer tokens than raw LLM browsing. This makes per-user economics viable even for daily active users performing 20-50 tasks per day.

**Q: What's your go-to-market?**
> We're starting with assistive technology centers and ALS/MS patient communities. These users have the highest urgency, the clearest need, and strong community networks for word-of-mouth adoption.

**Q: Can this work for non-disabled users?**
> Absolutely. Hands-free browsing is valuable for anyone — driving, cooking, multitasking. But our priority is the people who need it most.
