from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Senior Tier: Claude 3.5 Sonnet if key available, otherwise fallback to Gemini
anthropic_key = os.getenv("ANTHROPIC_API_KEY")
if anthropic_key and anthropic_key != "missing":
    senior = ChatAnthropic(
        model="claude-3-5-sonnet-20240620",
        max_tokens=8192,
        anthropic_api_key=anthropic_key
    )
else:
    senior = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        google_api_key=os.getenv("GOOGLE_API_KEY", "missing"),
        temperature=0.7
    )

# Fast Tier: Using local Ollama
from langchain_community.chat_models import ChatOllama
fast = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
    base_url=os.getenv("OLLAMA_URL", "http://localhost:11434")
)

# Gemini Tier: High Intelligence & Long Context
gemini = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
    google_api_key=os.getenv("GOOGLE_API_KEY", "missing"),
    temperature=0.7
)

def load_profile(agent_id: str) -> str:
    """Load the full markdown profile for an agent."""
    path = Path(__file__).parent.parent / "Onboarding" / "profiles" / f"{agent_id}-PROFILE-1.0.0.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"You are agent {agent_id}. Maintain your unique expert persona at all times."

# Master Roster - Core Active Team only
AGENTS = {
    "aria": {
        "id": "AGT-001",
        "name": "Aria",
        "title": "Chief Executive Officer (CEO)",
        "triggers": ["aria", "ceo", "strategy", "board", "vision", "coordinate", "final decision"],
        "llm": senior,
        "profile": load_profile("AGT-001"),
        "active": True,
        "owns": ["decision"]
    },
    "nadia": {
        "id": "AGT-004",
        "name": "Nadia",
        "title": "Planner / System Designer",
        "triggers": ["nadia", "strategic", "long term", "vision", "northern star", "plan"],
        "llm": senior,
        "profile": load_profile("AGT-004"),
        "active": True,
        "owns": ["planning"]
    },
    "tucker": {
        "id": "AGT-012",
        "name": "Tucker",
        "title": "Engineer",
        "triggers": ["tucker", "build", "code", "engineer", "implement", "architecture"],
        "llm": senior,
        "profile": load_profile("AGT-012"),
        "active": True,
        "owns": ["execution"]
    },
    "jenny": {
        "id": "AGT-009",
        "name": "Jenny",
        "title": "Executive Personal Assistant (PA)",
        "triggers": ["jenny", "schedule", "calendar", "email", "meeting", "book", "remind"],
        "llm": gemini, # Upgraded to Gemini for reliability
        "profile": load_profile("AGT-009"),
        "active": True,
        "owns": ["communication"]
    },
    "wall-e": {
        "id": "AGT-010",
        "name": "WALL-E",
        "title": "System Auditor / Compliance",
        "triggers": ["wall-e", "audit", "critique", "verify", "safety"],
        "llm": fast,
        "profile": load_profile("AGT-010"),
        "active": True,
        "owns": ["audit"]
    },
    "eli": {
        "id": "AGT-002",
        "name": "Eli",
        "title": "Chief Momentum Officer (CADO)",
        "triggers": ["eli", "overwhelm", "focus", "prioritise", "energy", "adhd", "momentum"],
        "llm": senior,
        "profile": load_profile("AGT-002"),
        "active": True,
        "owns": ["momentum"]
    },
    "owen": {
        "id": "AGT-008",
        "name": "Owen",
        "title": "Intelligence & Learning Officer",
        "triggers": ["owen", "analyse", "learn", "improve", "reflect", "data", "machine learning"],
        "llm": senior,
        "profile": load_profile("AGT-008"),
        "active": True,
        "owns": ["intelligence"]
    }
}

# Disabled latent agents (kept for reference but not routed)
LATENT_AGENTS = {
    "marcus": {"id": "AGT-003", "name": "Marcus"},
    "james": {"id": "AGT-005", "name": "James"},
    "leo": {"id": "AGT-007", "name": "Leo"},
    "elena": {"id": "AGT-006", "name": "Elena"},
    "jax": {"id": "AGT-011", "name": "Jax"},
    "clara": {"id": "AGT-021", "name": "Clara"},
    "victor": {"id": "AGT-022", "name": "Victor"},
    "reese": {"id": "AGT-020", "name": "Reese"}
}
