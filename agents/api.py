from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel
from typing import Optional, Dict
from .roster import AGENTS
from .orchestrator import Orchestrator
from .telemetry import TELEMETRY
import os

app = FastAPI(title="A.G.E.N.T.S. Interactive API")

# Enable CORS for the local web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Orchestrator
orc = Orchestrator()

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html?v=4.0.0")

class ChatRequest(BaseModel):
    message: str

@app.get("/status")
async def get_status():
    return {
        "status": "orchestration_active",
        "session_id": orc.session_id,
        "agents_total": len(AGENTS)
    }

@app.get("/agents")
async def list_agents():
    """List all available agents in the roster."""
    return [
        {"id": v["id"], "name": v["name"], "title": v["title"], "triggers": v["triggers"]}
        for k, v in AGENTS.items()
    ]

@app.get("/telemetry")
async def get_telemetry():
    """Return live token and cost stats in the new structured format."""
    return TELEMETRY.get_stats()

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """The unified multi-agent chat endpoint via Orchestrated streaming."""
    async def event_generator():
        try:
            async for token in orc.astream_chat(req.message):
                yield token
        except Exception as e:
            yield f"data: [ORCHESTRATOR ERROR] {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
