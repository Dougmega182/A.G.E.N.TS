import os
import requests
import time
import re
import sys

# Authorization: use environment variable or fallback to provided key
API_KEY = os.environ.get("GALAXY_AI_API_KEY", "gx_RApLuiaASzrgswRCS4tRSv")
BASE_URL = "https://api.galaxy.ai/api"

def get_opus_thinking(task: str) -> str:
    print("Initiating reasoning request...")

    # Call Galaxy AI direct model run endpoint
    response = requests.post(
        f"{BASE_URL}/v1/nodes/claude_sonnet_4_6/run",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        },
        json={
            "nodeType": "claude_sonnet_4_6",
            "input": {
                "prompt": task,
                "system_prompt": """
You are a reasoning-only engine embedded in the A.G.E.N.T.S project. Your sole function is to think — never to produce code, solutions, or conclusions.

PROJECT: A.G.E.N.T.S — Autonomous Governance & Execution Networked Task System
Build Rev: 3.7.0 | Domain: Construction Project Intelligence

WHAT IT IS:
A multi-agent decision engine for construction project management.
Pipeline: TRIGGER → PLAN → DECIDE → GATE → EXECUTE → AUDIT → LEARN
Every action is human-approved. Every decision is traceable. No agent acts autonomously.

AGENT ROSTER:
- Aria      → CEO / Strategy / Final decision authority
- Nadia     → Planner / Schedule and risk modelling
- Tucker    → Engineer / Technical implementation
- Jenny     → PA / Comms, Gmail drafts, Calendar
- WALL-E    → Auditor / Runs on every loop, pre and post
- Eli       → Momentum Engine / Velocity signals, logistics dispatch
- Owen      → ILO (background) / Negative pattern briefing, silent voting

CONSTITUTIONAL LAWS (non-negotiable):
G1  GATEKEEPER_SUPREMACY  — No action executes without human approval
G2  NO_LAYER_SKIPPING     — Agents cannot bypass the chain of command
G3  ZERO_HALLUCINATION    — No invented facts, no fabricated data
G4  AUDIT_FIRST           — WALL-E runs before and after every decision
G5  FULL_TRACEABILITY     — Every decision carries a trace ID and why-line
G6  SCOPE_INVIOLABILITY   — Agents stay inside their defined domain
G11 MOMENTUM_PROTECTION   — Eli signals are staged, never auto-dispatched

SYSTEM STATUS:
- Intelligence Level: 5 (Deterministic Actuation, Parameter-Abstracted, Context-Aware)
- Safety Level: 6 (Approval-Gated, Duplicate Suppression, Conflict Resolution active)
- Decision Cache (Layer 1): LIVE — 30% hit rate baseline, 67% LLM-call reduction on hits
- Semantic Expansion (Layer 2.6): LIVE — parameter abstraction, phrase mapping, canonical synonyms
- Bypass matrix: enforced on both read and write paths

CURRENT PHASE: Phase 2-Logistics — Momentum Actuation (85% complete)
CURRENT BOTTLENECK: Phase 2.6 — Seal the Cracks
- Conflict Resolver: entity + polarity detection preventing opposing dispatches ✅
- Recency Rule: newer signals override older conflicting intents ✅
- Stakeholder Targeting: automated domain routing ✅
- Concept Normalization: still being verified

WHAT IS NOT FINISHED:
- Phase 2.6 full verification (concept normalization edge cases)
- Phase 5.2 dashboard requires 20–50 real log_issue.py runs before building
- Phase 5.3 penalty decay: deferred until dashboard is stable
- Real-world cache hit rate: untested on live site issues

DO NOT suggest:
- New agents or new architectural layers
- Skipping the measurement gate before Phase 5.2
- Auto-dispatch of any agent action
- Changes to the bypass matrix or cache policy without data

THINKING RULES:
1. Begin every response with <thinking>
2. Reason step by step about the SPECIFIC problem given to you
3. Ground every inference in the project context above
4. Consider constitutional constraints — especially G1, G4, G5
5. Close with </thinking>
6. Write nothing after </thinking>
7. Never produce code, solutions, answers, or conclusions — only reasoning
""",
                "reasoning": True,
                "max_tokens": 8192,
                "temperature": 0.7,
                "image_urls": []
            }
        }
    )

    if response.status_code != 200:
        print(f"API Error ({response.status_code}): {response.text}")
        sys.exit(1)

    try:
        data = response.json()
        run_id = data.get("runId")
    except Exception as e:
        print(f"Error parsing start run response: {e}")
        print(f"Raw response: {response.text}")
        sys.exit(1)

    if not run_id:
        print(f"Error: Missing runId in API response. Full response: {data}")
        sys.exit(1)

    print(f"Run started successfully (ID: {run_id})")
    print("Awaiting convergence...", end="", flush=True)

    while True:
        poll = requests.get(
            f"{BASE_URL}/v1/nodes/runs/{run_id}",
            headers={"Authorization": f"Bearer {API_KEY}"}
        )

        if poll.status_code != 200:
            # Silently retry on transient poll errors
            time.sleep(5)
            continue

        try:
            data = poll.json()
        except Exception as e:
            time.sleep(5)
            continue

        status = data.get("status")

        if status == "COMPLETED":
            print(" [DONE]\n")
            out = data.get("output", {})
            
            # Robust extraction of the result text
            raw = None
            if isinstance(out, dict):
                if "output" in out: # Direct model run output key
                    raw = out["output"]
                elif "result" in out:
                    raw = out["result"][0] if isinstance(out["result"], list) else out["result"]
                elif "text" in out:
                    raw = out["text"]
                elif "response" in out:
                    raw = out["response"]
                elif "message" in out:
                    raw = out["message"]
            
            if raw is None:
                print(f"[DEBUG] Unexpected output structure from Galaxy AI: {out}")
                sys.exit(1)
            
            # Extract thinking block if present, otherwise return raw
            match = re.search(r"<thinking>(.*?)</thinking>", str(raw), re.DOTALL)
            return match.group(1).strip() if match else str(raw)

        elif status == "FAILED":
            print("\n")
            err_msg = data.get('error', 'Unknown error')
            raise Exception(f"Run failed: {err_msg}")

        print(".", end="", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        task = sys.argv[1]
    else:
        task = "\nExample questions for ProseLab:"
    
    try:
        thinking = get_opus_thinking(task)
        print("=== Opus Thinking ===")
        print(thinking)
    except Exception as e:
        print(f"\nExecution Error: {e}")
