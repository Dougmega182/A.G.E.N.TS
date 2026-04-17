"""
A.G.E.N.T.S. — Gatekeeper CLI
The command-line interface for the human Gatekeeper to interact with the system.
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime
import asyncio
import uuid

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich import box

from agents.core import GovernanceEngine, Agent, load_config, DATA_DIR, ensure_data_dirs
from agents.llm import LLMProvider
from agents.boardroom import Boardroom
from agents.sessions import SessionManager
from agents.logic.event_bus import LOG_ROOT

console = Console()

# ─── Banner ───────────────────────────────────────────────

BANNER = """
[bold cyan]
     █████╗  ██████╗ ███████╗███╗   ██╗████████╗███████╗
    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝
    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ███████╗
    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ╚════██║
    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ███████║
    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝[/]
[dim]    Autonomous Governance & Execution Networked Task System[/]
[dim]    BUILD REV: 2.0.0  |  DOMAINS: 9  |  GATEKEEPER: ACTIVE[/]
"""


def show_banner():
    console.print(BANNER)


def show_status(gov: GovernanceEngine):
    """Show system status overview."""
    table = Table(title="SYSTEM STATUS", box=box.SIMPLE_HEAVY, border_style="cyan")
    table.add_column("Component", style="bold cyan")
    table.add_column("Status", style="green")

    table.add_row("Constitution", f"{len(gov.constitution['laws'])} laws active")
    table.add_row("Protocols", f"{len(gov.protocols['protocols'])} armed")
    table.add_row("Domains", f"{len(gov.departments['domain_divisions'])} active")
    table.add_row("Board Agents", f"{len(gov.voting['voting_framework']['vote_weights'])} seated")

    # Count pending items
    ensure_data_dirs()
    proposals = list((DATA_DIR / "proposals").glob("*.json"))
    tasks = list((DATA_DIR / "tasks").glob("*.json"))
    pending_proposals = sum(1 for p in proposals if json.loads(p.read_text()).get("gatekeeper_decision") is None)
    pending_tasks = sum(1 for t in tasks if json.loads(t.read_text()).get("status") == "queued")

    table.add_row("Pending Proposals", f"[yellow]{pending_proposals}[/]" if pending_proposals else "0")
    table.add_row("Queued Tasks", f"[yellow]{pending_tasks}[/]" if pending_tasks else "0")

    console.print(table)


def show_domains(gov: GovernanceEngine):
    """Show domain health dashboard."""
    table = Table(title="DOMAIN HEALTH", box=box.ROUNDED, border_style="cyan")
    table.add_column("", width=3)
    table.add_column("Domain", style="bold")
    table.add_column("Status", style="green")

    for domain in gov.departments["domain_divisions"]:
        table.add_row(domain["icon"], domain["name"], "● ONLINE")

    console.print(table)


def show_constitution(gov: GovernanceEngine):
    """Display constitutional laws."""
    console.print("\n[bold cyan]═══ CONSTITUTIONAL LAWS ═══[/]\n")
    for law in gov.constitution["laws"]:
        severity_color = {
            "ABSOLUTE": "red", "CRITICAL": "red", "CONSTITUTIONAL": "yellow",
            "MANDATORY": "yellow", "HIGH": "blue", "PROTECTED": "green"
        }.get(law["severity"], "white")
        override = "🔒 NO" if law["overrideable"] is False else f"⚠ {law['overrideable']}"
        console.print(Panel(
            f"[bold]{law['rule']}[/]\n\n"
            f"[dim]Severity:[/] [{severity_color}]{law['severity']}[/]  |  "
            f"[dim]Override:[/] {override}",
            title=f"[bold cyan]{law['id']}: {law['name']}[/]",
            border_style=severity_color
        ))


def show_protocols(gov: GovernanceEngine):
    """Display protocol definitions."""
    console.print("\n[bold cyan]═══ PROTOCOL FRAMEWORK ═══[/]\n")
    for proto in gov.protocols["protocols"]:
        color = {
            "RED-1": "red", "BLUE-1": "blue", "GOLD-1": "yellow",
            "BLACK-1": "white", "AMBER-1": "dark_orange", "GREEN-1": "green", "WHITE-1": "bright_white"
        }.get(proto["id"], "white")
        console.print(Panel(
            f"[bold]TRIGGER:[/] {proto['trigger']}\n\n"
            f"[bold]ACTION:[/] {proto['action']}\n\n"
            f"[dim]Steps:[/]\n" + "\n".join(f"  → {s}" for s in proto["steps"]),
            title=f"[bold {color}]{proto['id']}: {proto['name']}[/]",
            border_style=color
        ))


def approve_proposals(gov: GovernanceEngine):
    """Show pending proposals for Gatekeeper approval."""
    ensure_data_dirs()
    proposals_dir = DATA_DIR / "proposals"
    pending = []

    for pf in proposals_dir.glob("*.json"):
        prop = json.loads(pf.read_text())
        if prop.get("gatekeeper_decision") is None and prop.get("status") != "rejected_constitutional":
            pending.append((pf, prop))

    if not pending:
        console.print("[dim]No pending proposals.[/]")
        return

    for pf, prop in pending:
        # Check for vote record
        vote_file = DATA_DIR / "votes" / f"{prop['proposal_id']}.json"
        vote_info = ""
        if vote_file.exists():
            votes = json.loads(vote_file.read_text())
            vote_info = f"\n[bold]Board Vote:[/] YES {votes['yes_weight']:.1f} / NO {votes['no_weight']:.1f} → {votes['decision']}"

        console.print(Panel(
            f"[bold]Title:[/] {prop['title']}\n"
            f"[bold]Domain:[/] {prop['domain']}\n"
            f"[bold]Impact:[/] {prop['impact']}\n"
            f"[bold]Created by:[/] {prop['created_by']}\n"
            f"[bold]Description:[/] {prop['description']}"
            f"{vote_info}",
            title=f"[bold cyan]{prop['proposal_id']}[/]",
            border_style="cyan"
        ))

        decision = Prompt.ask(
            "  👑 Gatekeeper Decision",
            choices=["approve", "reject", "skip"],
            default="skip"
        )

        if decision in ("approve", "reject"):
            prop["gatekeeper_decision"] = decision.upper()
            prop["gatekeeper_decided_at"] = datetime.utcnow().isoformat()
            prop["status"] = "approved" if decision == "approve" else "rejected"
            with open(pf, "w", encoding="utf-8") as f:
                json.dump(prop, f, indent=2)
            color = "green" if decision == "approve" else "red"
            console.print(f"  [{color}]✓ {decision.upper()}[/]\n")


async def create_proposal_flow_stateful(gov: GovernanceEngine, manager: SessionManager):
    """Interactive flow to initiate a stateful LangGraph session."""
    console.print("\n[bold cyan]═══ INITIATE SESSION ═══[/]\n")

    title = Prompt.ask("  Title")
    description = Prompt.ask("  Description")

    # Show domain options
    domains = [d["id"] for d in gov.departments["domain_divisions"]]
    domain = Prompt.ask("  Domain", choices=domains)
    impact = Prompt.ask("  Impact", choices=["low", "medium", "high", "critical"], default="medium")

    # Create the base proposal object
    proposal_id = f"PRP-{datetime.utcnow().strftime('%y%m%d%H%M%S')}"
    proposal = {
        "proposal_id": proposal_id,
        "title": title,
        "description": description,
        "domain": domain,
        "impact": impact,
        "created_by": "AGT-001",
        "created_at": datetime.utcnow().isoformat(),
        "status": "pending"
    }

    thread_id = f"THD-{uuid.uuid4().hex[:8]}"
    console.print(f"\n[bold green]✓ Initialising Session: {thread_id}[/]")
    console.print("[dim]  The graph will now process logic, planning, and governance layers...[/]\n")

    # Start the async run in the background
    # We use a task so the CLI remains responsive for status checks,
    # but for first-time feedback, we can wait a few seconds or just tell them to check Pending.
    asyncio.create_task(manager.run_proposal(proposal, thread_id))
    
    console.print(f"  [cyan]●[/] Background execution started.")
    console.print(f"  [cyan]●[/] Monitor progress in [bold]Pending Graph Actions[/] or [bold]Status[/].\n")



def show_tasks(gov: GovernanceEngine):
    """Show the task queue."""
    ensure_data_dirs()
    tasks_dir = DATA_DIR / "tasks"
    tasks = []

    for tf in tasks_dir.glob("*.json"):
        task = json.loads(tf.read_text())
        tasks.append(task)

    if not tasks:
        console.print("[dim]No tasks in queue.[/]")
        return

    table = Table(title="TASK QUEUE", box=box.ROUNDED, border_style="cyan")
    table.add_column("ID", style="cyan", width=24)
    table.add_column("Domain", style="blue")
    table.add_column("Description")
    table.add_column("Priority")
    table.add_column("Energy")
    table.add_column("Status")

    priority_colors = {"critical": "red", "high": "yellow", "medium": "blue", "low": "green"}

    for task in sorted(tasks, key=lambda t: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(t.get("priority", "low"), 4)):
        pc = priority_colors.get(task.get("priority", "low"), "white")
        table.add_row(
            task["task_id"],
            task.get("domain", "—"),
            task.get("description", "—")[:50],
            f"[{pc}]{task.get('priority', '—').upper()}[/]",
            task.get("energy_cost", "—"),
            task.get("status", "—")
        )

    console.print(table)


async def show_pending_graph_actions(manager: SessionManager):
    """Scan SQLite for sessions waiting for Gatekeeper input."""
    console.print("\n[bold cyan]═══ PENDING GRAPH ACTIONS ═══[/]\n")
    
    pending = []
    # alist() returns an async iterator of CheckpointTuple
    async for checkpoint_tuple in manager.checkpointer.alist(None):
        config = checkpoint_tuple.config
        checkpoint = checkpoint_tuple.checkpoint
        thread_id = config["configurable"]["thread_id"]
        
        # Get current state to see if it's waiting for gatekeeper
        state = await manager.app.aget_state(config)
        if state.next and "gatekeeper" in state.next:
            pending.append((thread_id, state))

    if not pending:
        console.print("[dim]No sessions waiting for Gatekeeper approval.[/]")
        return

    for thread_id, state in pending:
        data = state.values
        proposal = data.get("proposal", {})
        votes = data.get("votes", {})
        
        console.print(Panel(
            f"[bold]Session ID:[/] {thread_id}\n"
            f"[bold]Proposal:[/] {proposal.get('title', 'Untitled')}\n"
            f"[bold]Board Vote:[/] YES {votes.get('yes_weight', 0):.1f} / NO {votes.get('no_weight', 0):.1f} → {votes.get('decision', 'PENDING')}\n"
            f"[bold]Status:[/] [yellow]WAITING FOR GATEKEEPER[/]",
            title=f"[bold cyan]{proposal.get('proposal_id', '???')}[/]",
            border_style="yellow"
        ))

        if Confirm.ask(f"  Review session {thread_id} now?", default=True):
            decision = Prompt.ask(
                "  👑 Decision",
                choices=["APPROVE", "REJECT", "SKIP"],
                default="SKIP"
            )
            
            if decision in ("APPROVE", "REJECT"):
                reason = Prompt.ask("  Reason (optional)")
                console.print("\n[dim]  Injecting decision and resuming graph...[/]")
                await manager.provide_decision(thread_id, decision, reasoning=reason)
                console.print(f"[green]✓ Decision '{decision}' executed.[/]")


async def main_loop():
    """Main CLI loop for the Gatekeeper."""
    show_banner()

    try:
        gov = GovernanceEngine()
        manager = await SessionManager.create()
    except Exception as e:
        console.print(f"[red]Initialisation error: {e}[/]")
        return

    # Determine LLM provider
    provider = os.getenv("LLM_PROVIDER", "ollama")
    try:
        llm = LLMProvider(provider=provider)
        console.print(f"[dim]  LLM: {provider} ({llm.model})[/]\n")
    except Exception as e:
        console.print(f"[yellow]  LLM not configured: {e}[/]")
        llm = None

    show_status(gov)

    while True:
        console.print("\n[bold cyan]COMMAND CENTRE[/]")
        console.print("[dim]  1. Status        2. Domains       3. Constitution[/]")
        console.print("[dim]  4. Protocols     5. Proposals     6. New Proposal[/]")
        console.print("[dim]  7. Tasks         8. Audit Log     9. Exit[/]")
        console.print("[dim]  10. [bold yellow]Pending Graph Actions[/][/]")

        choice = Prompt.ask("\n  👑", choices=["1","2","3","4","5","6","7","8","9","10"], default="1")

        if choice == "1":
            show_status(gov)
        elif choice == "10":
            await show_pending_graph_actions(manager)
        elif choice == "2":
            show_domains(gov)
        elif choice == "3":
            show_constitution(gov)
        elif choice == "4":
            show_protocols(gov)
        elif choice == "5":
            approve_proposals(gov)
        elif choice == "6":
            if llm:
                await create_proposal_flow_stateful(gov, manager)
            else:
                console.print("[red]LLM not configured.[/]")
        elif choice == "7":
            show_tasks(gov)
        elif choice == "8":
            # Show audit log
            ensure_data_dirs()
            log_file = LOG_ROOT / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            if log_file.exists():
                console.print(f"\n[bold cyan]═══ AUDIT LOG ({datetime.now().strftime('%Y-%m-%d')}) ═══[/]\n")
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            ts = entry.get('timestamp','?')[:19].replace('T', ' ')
                            agent = entry.get('agent_id','?')
                            event = entry.get('event_type','?')
                            msg = entry.get('status', entry.get('decision', ''))
                            console.print(f"  [dim]{ts}[/] [bold cyan]{agent:7}[/] [yellow]{event:15}[/] {msg}")
                        except:
                            continue
            else:
                console.print("[dim]No audit log for today.[/]")
        elif choice == "9":
            await manager.close()
            break


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        console.print("\n[dim]  Gatekeeper disconnected. System remains governed.[/]\n")
