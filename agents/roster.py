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
    # Fallback to Gemini for the entire senior tier
    senior = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GOOGLE_API_KEY", "missing"),
        temperature=0.7
    )

# Fast Tier: Using local Ollama (via LangChain's OpenAI compatibility or Ollama class)
# Standardizing on local performance to ensure zero-lag routing
from langchain_community.chat_models import ChatOllama
fast = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
    base_url=os.getenv("OLLAMA_URL", "http://localhost:11434")
)

# Gemini Tier: High Intelligence & Long Context (Phase 7)
gemini = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY", "missing"),
    temperature=0.7
)

def load_profile(agent_id: str) -> str:
    """Load the full markdown profile for an agent."""
    path = Path(__file__).parent.parent / "Onboarding" / "profiles" / f"{agent_id}-PROFILE-1.0.0.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return f"You are agent {agent_id}. Maintain your unique expert persona at all times."

# Master Roster of Agents always present in the room
AGENTS = {
    "aria": {
        "id": "AGT-001",
        "name": "Aria",
        "title": "CEO",
        "triggers": ["aria", "ceo", "strategy", "board", "coordinate"],
        "llm": senior,
        "profile": load_profile("AGT-001"),
        "tools": []
    },
    "marcus": {
        "id": "AGT-003",
        "name": "Marcus",
        "title": "Chief Audit Officer",
        "triggers": ["marcus", "audit", "compliance", "veto", "review", "check"],
        "llm": senior,
        "profile": load_profile("AGT-003"),
        "tools": []
    },
    "eli": {
        "id": "AGT-002",
        "name": "Eli",
        "title": "Chief ADHD Officer",
        "triggers": ["eli", "overwhelm", "focus", "prioritise", "energy", "adhd", "momentum"],
        "llm": senior,
        "profile": load_profile("AGT-002"),
        "tools": []
    },
    "jenny": {
        "id": "AGT-009",
        "name": "Jenny",
        "title": "Personal Assistant",
        "triggers": ["jenny", "schedule", "calendar", "email", "meeting", "book", "remind"],
        "llm": fast,
        "profile": load_profile("AGT-009"),
        "tools": []
    },
    "owen": {
        "id": "AGT-008",
        "name": "Owen",
        "title": "Intelligence & Learning",
        "triggers": ["owen", "analyse", "learn", "improve", "reflect", "data", "code", "build", "write"],
        "llm": senior,
        "profile": load_profile("AGT-008"),
        "tools": []
    },
    "nadia": {
        "id": "AGT-004",
        "name": "Nadia",
        "title": "Chief Strategy Officer",
        "triggers": ["nadia", "strategic", "northern star", "long term", "vision", "plan"],
        "llm": senior,
        "profile": load_profile("AGT-004"),
        "tools": []
    },
    "james": {
        "id": "AGT-005",
        "name": "James",
        "title": "Chief Risk Officer",
        "triggers": ["james", "risk", "threat", "danger", "worst case", "exposure"],
        "llm": senior,
        "profile": load_profile("AGT-005"),
        "tools": []
    },
    "leo": {
        "id": "AGT-007",
        "name": "Leo",
        "title": "Chief Technology Officer",
        "triggers": ["leo", "tech", "architecture", "infrastructure", "system", "technical"],
        "llm": gemini,
        "profile": load_profile("AGT-007"),
        "tools": []
    },
    "clara": {
        "id": "AGT-021",
        "name": "Clara",
        "title": "Chief Integrity Officer",
        "triggers": ["clara", "integrity", "truth", "verify", "fact check", "honest"],
        "llm": senior,
        "profile": load_profile("AGT-021"),
        "tools": []
    },
    "victor": {
        "id": "AGT-022",
        "name": "Victor",
        "title": "CISO",
        "triggers": ["victor", "security", "breach", "threat", "cyber", "protect"],
        "llm": fast,
        "profile": load_profile("AGT-022"),
        "tools": []
    },
    "jax": {
        "id": "AGT-011",
        "name": "Jax",
        "title": "Content Generation",
        "triggers": ["jax", "write", "create", "generate", "content", "creative"],
        "llm": gemini,
        "profile": load_profile("AGT-011"),
        "tools": []
    },
    "reese": {
        "id": "AGT-020",
        "name": "Reese",
        "title": "Interrogation Lead",
        "triggers": ["reese", "challenge", "stress test", "question", "poke holes", "devil"],
        "llm": senior,
        "profile": load_profile("AGT-020"),
        "tools": []
    },
    "elena": {
        "id": "AGT-006",
        "name": "Elena",
        "title": "Chief Operations Officer",
        "triggers": ["elena", "operations", "resources", "capacity", "timeline", "delivery"],
        "llm": gemini,
        "profile": load_profile("AGT-006"),
        "tools": []
    }
}
