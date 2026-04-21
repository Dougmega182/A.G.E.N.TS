![alt text](image.png)
---

## Phase 3a — Voice synthesis pipeline (backend)

This is your foundation. Before anything talks to Android, you need text going in and Jenny's voice coming out.

**What you're building:** a `/synthesise` API endpoint that accepts text and returns an audio file.

The stack: Piper TTS (fast, free, runs locally) as the base voice generator → piped into your existing RVC model → audio file returned. You already have the hardest part (RVC + voice model), so this phase is mostly wiring.

Deliverable: `curl -d "text=Good morning Dale"` → plays Jenny's voice. That's your Phase 3a done test.

---

## Phase 3b — Jenny intelligence layer (backend)

This is where she gets her brain. You're building a `/ask-jenny` FastAPI endpoint that receives a text query, spins up the Jenny agent (AGT-009 profile as system prompt), pulls your Google Calendar via the MCP you already have connected, pulls pending A.G.E.N.T.S. tasks, and returns a natural language response.

For "what's my day look like today?" the response flow is: Calendar events → task queue → Jenny formats a morning brief → returns plain text. That text then goes straight to Phase 3a's synthesis endpoint.

Deliverable: POST `{"query": "what's my day look like today?"}` → returns Jenny's spoken brief as audio.

---

## Phase 3c — Android interface (two paths)

**Quick path — Tasker + AutoVoice (days, no coding):** Tasker is an Android automation app. AutoVoice adds a custom wake word layer. You set "Jenny" as the trigger, Tasker captures your speech, fires an HTTP request to your Phase 3b endpoint, receives audio back, and plays it. No Android Studio, no APK. This gets you 80% of the experience in a fraction of the time — ideal for validating the full pipeline before investing in a proper app.

**Proper path — native Android app (weeks, some Kotlin):** A lightweight app running a background service with Picovoice Porcupine for always-on "Jenny" wake word detection (they have a free tier and support custom wake words), Android's built-in SpeechRecognizer for STT (free, fast, no API key), HTTP client to your backend, and ExoPlayer for audio playback. This is the production-grade version.

Given your ADHD profile (G8), the strong recommendation is to start with Tasker to prove the pipeline works end-to-end, then graduate to the native app once you've heard Jenny answer you on your phone. That dopamine hit first — code quality second.

---

## Phase 3d — Polish and reliability

Latency tuning (target under 3 seconds start to finish), error handling when there's no network, a loading indicator so you know she heard you, and optionally a simple home screen widget with a "Jenny" button for days when voice feels like too much friction.

---

## Recommended tech stack

| Component | Tool | Cost |
|---|---|---|
| Wake word | Picovoice Porcupine (Tasker first) | Free tier |
| STT | Android SpeechRecognizer | Free |
| Backend | FastAPI (Python) | Free |
| Base TTS | Piper TTS | Free / local |
| Voice synthesis | Your existing RVC model | Done |
| Android (quick) | Tasker + AutoVoice | ~$7 one-time |
| Android (proper) | Native Kotlin app | Dev time only |

---

## Single next action

Get Phase 3a running first. Set up a local FastAPI server with a `/synthesise` endpoint, pipe a test string through Piper TTS, then through your RVC model, and confirm you get Jenny's voice out the other end. Everything else builds on top of that.

Want me to draft the FastAPI scaffold for Phase 3a to get you started right now?