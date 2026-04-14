from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from agents.graph import build_agents_graph
import uuid

class SessionManager:
    """
    Manages A.G.E.N.T.S. graph sessions using SQLite persistence.
    """
    def __init__(self, db_path: str = "data/agents_state.db"):
        self.db_path = db_path
        # AsyncSqliteSaver is the correct async-compatible checkpointer
        self._saver_context = AsyncSqliteSaver.from_conn_string(db_path)
        self.checkpointer = None # Will be initialized in an async factory or first use
        self.app = None

    @classmethod
    async def create(cls, db_path: str = "data/agents_state.db"):
        """Async factory to handle proper checkpointer lifetime."""
        self = cls(db_path)
        self.checkpointer = await self._saver_context.__aenter__()
        self.app = build_agents_graph(checkpointer=self.checkpointer)
        return self

    async def close(self):
        """Cleanly close the database connection."""
        if self._saver_context:
            await self._saver_context.__aexit__(None, None, None)

    def create_session(self) -> str:
        """Generate a new thread ID for a proposal session."""
        return str(uuid.uuid4())

    async def run_proposal(self, proposal: dict, thread_id: str):
        """Run or resume a proposal through the graph."""
        config = {"configurable": {"thread_id": thread_id}}
        
        # Check if we have an existing state to resume from
        state = await self.app.aget_state(config)
        
        if not state or not state.values:
            # New run — Initialize strict, versioned state
            initial_state = {
                "schema_version": "1.0.0",
                "session_id": thread_id,
                "status": "PENDING",
                "proposal": proposal,
                "current_layer": 0,
                "violations": [],
                "audit_trail": [],
                "protocol_triggered": None,
                "gatekeeper_decision": None,
                "gatekeeper_reasoning": None,
                "energy_state": "normal",
                "flow_state_active": False,
                "overwhelm_detected": False,
                "votes": {}
            }
            # Log transition start
            print(f"[{thread_id}] Starting new session v1.0.0")
            return await self.app.ainvoke(initial_state, config)
        else:
            # Resume run (e.g. after interrupt)
            print(f"[{thread_id}] Resuming existing session")
            return await self.app.ainvoke(None, config)

    async def get_state(self, thread_id: str):
        """Fetch the current context-complete state of a session."""
        config = {"configurable": {"thread_id": thread_id}}
        return await self.app.aget_state(config)

    async def provide_decision(self, thread_id: str, decision: str, reasoning: str = None):
        """
        Provide human decision to a paused graph.
        Strictly write-only: Updates state before resuming.
        """
        config = {"configurable": {"thread_id": thread_id}}
        
        # 1. Write the decision to the state
        update = {
            "gatekeeper_decision": decision,
            "gatekeeper_reasoning": reasoning,
            "status": "WAITING_FOR_RESUMPTION"
        }
        await self.app.aupdate_state(config, update)
        print(f"[{thread_id}] Decision '{decision}' injected into state.")
        
        # 2. Resume the runner
        return await self.app.ainvoke(None, config)
